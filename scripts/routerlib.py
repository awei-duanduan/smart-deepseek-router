"""Local routing and Git verification. Python 3.10+, standard library only.

Original implementation; SDK adapter follows deepseek-ai/deepseek-harness.
Git worktrees and post-run scope checks are NOT an OS security sandbox.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import sys
import tempfile

from credentials import runtime_dir
from provider_proxy import BoundedCredentialProxy, discover_models, load_capabilities, save_capabilities, select_models

VERSION = "0.8.1"
TRAITS = ("bounded", "verifiable", "independent", "dependency_stable", "repetitive", "context_heavy")
BLOCKERS = ("secrets", "deployment", "destructive", "external_side_effects", "policy_decision", "unverifiable")
WEIGHTS = dict(bounded=3, verifiable=3, independent=2, dependency_stable=2, repetitive=1, context_heavy=1)
SENSITIVE = re.compile(r"(^|/)(\.git|\.env(?:\..*)?|\.ssh|\.aws|\.azure|\.npmrc|\.pypirc|credentials(?:\.(?:json|ya?ml|toml|ini|conf|txt|xml|db|sqlite|enc))?|service-account(?:\.(?:json|ya?ml|toml|ini|conf|txt|xml|db|sqlite|enc))?|id_rsa|id_ed25519|kubeconfig|terraform\.tfstate)(/|$)|\.(pem|key|p12|pfx|kdbx)$", re.I)
SECRET = re.compile(r"sk-[A-Za-z0-9_-]{12,}|-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")
INFRA = re.compile(r"ModuleNotFoundError|ImportError|command not found|not recognized as|PermissionError|permission denied|No such file or directory|ConnectionError|connection refused|ENOSPC|out of memory|Cannot find module", re.I)
CONTRACT_FIELDS = {
    "schema_version", "id", "objective", "scope", "acceptance", "preflight_verifiers", "acceptance_verifiers",
    "verifier_paths", "allow_pro", "allow_noop", "model_policy", "task_timeout_seconds", "max_provider_requests",
    "max_model_output_tokens", "max_changed_files", "max_changed_bytes", "max_patch_bytes", "routing_score",
}
TASK_FIELDS = (CONTRACT_FIELDS - {"schema_version"}) | {"traits", "blockers", "depends_on"}
VERIFIER_FIELDS = {"argv", "cwd", "timeout_seconds", "implementation_failure_pattern"}
DEFAULT_LIMITS = dict(max_provider_requests=24, max_model_output_tokens=8192, max_changed_files=200, max_changed_bytes=20 * 1024 * 1024, max_patch_bytes=40 * 1024 * 1024)
MAX_PLAN_TASKS = 32


class RouterError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise RouterError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def clean_env():
    # Avoid passing account credentials to verifiers or workers.
    keys = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "LANG", "LC_ALL", "VIRTUAL_ENV"}
    result = {k: v for k, v in os.environ.items() if k.upper() in keys}
    result.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", GIT_TERMINAL_PROMPT="0")
    return result


def resolved(path):
    """Resolve links while keeping paths acceptable to Git for Windows."""
    value = str(Path(path).resolve())
    if os.name == "nt" and value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif os.name == "nt" and value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value)


def redact(text):
    for key, value in os.environ.items():
        if len(value) >= 8 and re.search(r"KEY|TOKEN|SECRET|PASSWORD", key, re.I):
            text = text.replace(value, "[REDACTED]")
    return SECRET.sub("[REDACTED]", text)


def command(argv, cwd, timeout=60, env=None):
    """No shell interpolation; bound the complete process tree on timeout."""
    opts = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    # Disk-backed output avoids unbounded RAM from a noisy child.
    with tempfile.TemporaryFile() as output:
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env or clean_env(), stdout=output, stderr=subprocess.STDOUT, **opts)
        except OSError as exc:
            return {"kind": "infrastructure", "exit_code": None, "output": redact(str(exc))}
        try:
            code = proc.wait(timeout=timeout)
            kind = "completed"
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)
            code, kind = None, "timeout"
        output.seek(0, 2)
        output.seek(max(0, output.tell() - 65536))
        return {"kind": kind, "exit_code": code, "output": redact(output.read().decode("utf-8", errors="replace"))}


def git(repo, *args, env=None):
    result = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(repo), *args], env=env or clean_env(), capture_output=True, timeout=60)
    if result.returncode:
        raise RouterError(redact(result.stderr.decode("utf-8", errors="replace").strip()))
    return result.stdout


def root(path):
    path = resolved(path)
    found = resolved(git(path, "rev-parse", "--show-toplevel").decode().strip())
    require(found == path, "--workdir must name the Git repository root")
    git(path, "rev-parse", "--verify", "HEAD")
    return path


def clean(repo, reject_ignored=False):
    require(not git(repo, "status", "--porcelain=v1", "--untracked-files=all"), "Worktree is dirty; preserve user changes and keep this task in Codex or prepare a separate authorized clean checkout")
    require(not any(line.startswith("160000 ") for line in git(repo, "ls-files", "--stage").decode().splitlines()), "Submodule repositories are not supported by this router")
    if reject_ignored:
        require(not git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"), "Direct worker checkout contains ignored files; preserve them and use isolated worktree dispatch")


def outside(repo, path):
    path = resolved(path)
    require(not path.is_relative_to(resolved(repo)), "Run/output directory must be outside the repository")
    return path


@contextlib.contextmanager
def lock(repo):
    common = Path(git(repo, "rev-parse", "--git-common-dir").decode().strip())
    if not common.is_absolute():
        common = repo / common
    path = common.resolve() / "smart-deepseek-router.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RouterError("Another router run holds the repository lock; inspect a stale lock before removing it")
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def relative(value, directory=False):
    require(isinstance(value, str) and value and "\\" not in value, "Use non-empty repository-relative POSIX paths")
    p = PurePosixPath(value)
    require(not p.is_absolute() and all(x not in ("..", ".", "") for x in value.rstrip("/").split("/")), "Path traversal or empty path component")
    require(not any(c in value for c in ":*?[]\x00\n\r"), "Globs, drive paths, and control characters are not supported")
    require(directory or not value.endswith("/"), "Expected an exact file path")
    require(not SENSITIVE.search(value), "Sensitive paths cannot be delegated")
    return value


def contains(scope, path):
    # Case-fold conservatively, including on POSIX, to make plans portable.
    s, p = scope.casefold(), path.casefold()
    return p.startswith(s) if s.endswith("/") else p == s


def overlap(a, b):
    return a.rstrip("/").casefold() == b.rstrip("/").casefold() or contains(a, b.rstrip("/")) or contains(b, a.rstrip("/"))


def validate_contract(c):
    require(isinstance(c, dict), "Contract must be an object")
    require(not (set(c) - CONTRACT_FIELDS), "Unknown contract fields: " + ", ".join(sorted(set(c) - CONTRACT_FIELDS)))
    require(c.get("schema_version") == 2, "Unsupported contract schema_version; expected 2")
    require(isinstance(c.get("id"), str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", c["id"]), "Invalid task id")
    require(isinstance(c.get("objective"), str) and c["objective"].strip(), "Objective is required")
    for key in ("scope", "acceptance", "acceptance_verifiers"):
        require(isinstance(c.get(key), list) and c[key], f"{key} must be a non-empty list")
    require(isinstance(c.get("preflight_verifiers", []), list), "preflight_verifiers must be a list")
    require(all(isinstance(s, str) and s.strip() for s in c["acceptance"]), "Acceptance criteria must be text")
    for s in c["scope"]:
        relative(s, directory=True)
    for s in c.get("verifier_paths", []):
        relative(s)
        require(not any(contains(x, s) for x in c["scope"]), "Trusted verifier files must be outside the write scope")
    for v in c.get("preflight_verifiers", []) + c["acceptance_verifiers"]:
        require(isinstance(v, dict), "Each verifier must be an object")
        require(not (set(v) - VERIFIER_FIELDS), "Unknown verifier fields: " + ", ".join(sorted(set(v) - VERIFIER_FIELDS)))
        require(isinstance(v, dict) and isinstance(v.get("argv"), list) and v["argv"] and all(isinstance(a, str) and a and "\x00" not in a for a in v["argv"]), "Verifier requires a non-empty argv list")
        require(type(v.get("timeout_seconds", 120)) is int and 1 <= v.get("timeout_seconds", 120) <= 3600, "Verifier timeout must be 1..3600 seconds")
        relative(v["cwd"], directory=True) if v.get("cwd") not in (None, ".") else None
        if v.get("implementation_failure_pattern"):
            require(isinstance(v["implementation_failure_pattern"], str), "Failure pattern must be a string")
            try:
                re.compile(v["implementation_failure_pattern"])
            except re.error as exc:
                raise RouterError("Invalid implementation failure pattern") from exc
    require(type(c.get("allow_pro", False)) is bool, "allow_pro must be boolean")
    require(type(c.get("allow_noop", False)) is bool, "allow_noop must be boolean")
    require(c.get("model_policy", "auto") in ("auto", "flash-first", "pro-only"), "model_policy must be auto, flash-first or pro-only")
    require(type(c.get("routing_score", 0)) is int and 0 <= c.get("routing_score", 0) <= 12, "routing_score must be 0..12")
    require(type(c.get("task_timeout_seconds", 600)) is int and 1 <= c.get("task_timeout_seconds", 600) <= 3600, "Task timeout must be 1..3600 seconds")
    limits = dict(DEFAULT_LIMITS)
    limits.update({k: c[k] for k in DEFAULT_LIMITS if k in c})
    ranges = {
        "max_provider_requests": (1, 100), "max_model_output_tokens": (512, 32768),
        "max_changed_files": (1, 10000), "max_changed_bytes": (1, 1024 ** 3),
        "max_patch_bytes": (1, 2 * 1024 ** 3),
    }
    for key, (low, high) in ranges.items():
        require(type(limits[key]) is int and low <= limits[key] <= high, f"{key} must be {low}..{high}")
    require(not SECRET.search(json.dumps(c)), "Possible credential in contract; remove it and use environment credential storage")
    normalized = dict(c)
    normalized.setdefault("preflight_verifiers", [])
    normalized.setdefault("allow_pro", False)
    normalized.setdefault("allow_noop", False)
    normalized.setdefault("model_policy", "auto")
    normalized.setdefault("routing_score", 0)
    normalized.setdefault("task_timeout_seconds", 600)
    for key, value in limits.items():
        normalized.setdefault(key, value)
    return normalized


def compile_plan(plan):
    require(isinstance(plan, dict), "Plan must be an object")
    require(not (set(plan) - {"schema_version", "tasks"}), "Unknown plan fields")
    require(plan.get("schema_version") == 2, "Plan schema_version must be 2")
    require(isinstance(plan.get("tasks"), list) and 1 <= len(plan["tasks"]) <= MAX_PLAN_TASKS, f"Plan needs 1..{MAX_PLAN_TASKS} tasks")
    decisions, contracts, ids = [], [], set()
    for task in plan["tasks"]:
        require(isinstance(task, dict), "Each task must be an object")
        require(not (set(task) - TASK_FIELDS), "Unknown task fields: " + ", ".join(sorted(set(task) - TASK_FIELDS)))
        c = {k: task[k] for k in CONTRACT_FIELDS if k != "schema_version" and k in task}
        c["schema_version"] = 2
        c = validate_contract(c)
        require(c["id"] not in ids, "Duplicate task id")
        ids.add(c["id"])
        traits = task.get("traits", {})
        require(set(traits) == set(TRAITS) and all(type(v) is bool for v in traits.values()), "Specify all six routing traits as booleans")
        blockers = task.get("blockers", [])
        require(isinstance(blockers, list) and all(b in BLOCKERS for b in blockers), "Unknown blocker")
        deps = task.get("depends_on", [])
        require(isinstance(deps, list) and all(isinstance(x, str) for x in deps), "depends_on must be an id list")
        score = sum(WEIGHTS[k] for k, value in traits.items() if value)
        c.setdefault("routing_score", score)
        c.setdefault("model_policy", "auto")
        delegate = not blockers and traits["bounded"] and traits["verifiable"] and score >= 6
        decisions.append(dict(id=c["id"], score=score, route="deepseek" if delegate else "codex", blockers=blockers, depends_on=deps, parallel_eligible=delegate and traits["independent"] and traits["dependency_stable"] and not deps))
        if delegate:
            contracts.append(c)
    for d in decisions:
        require(all(x in ids and x != d["id"] for x in d["depends_on"]), "Invalid dependency")
    graph = {d["id"]: d["depends_on"] for d in decisions}
    visiting, visited = set(), set()
    def walk(node):
        require(node not in visiting, "Dependency cycle detected")
        if node in visited:
            return
        visiting.add(node)
        for dep in graph[node]:
            walk(dep)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        walk(node)
    # Dependencies are deliberately returned for Codex, not automatically scheduled.
    conflicts = []
    for i, a in enumerate(contracts):
        for b in contracts[i + 1:]:
            if any(overlap(x, y) for x in a["scope"] for y in b["scope"]):
                conflicts.append([a["id"], b["id"]])
    return dict(version=VERSION, decisions=decisions, contracts=contracts, conflicts=conflicts)


def save_plan(plan, out):
    compiled = compile_plan(plan)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "routing.json", compiled)
    for c in compiled["contracts"]:
        write_json(out / "contracts" / (c["id"] + ".json"), c)
    return compiled


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(repo, include_ignored=False):
    paths = git(repo, "ls-files", "-c", "-o", "--exclude-standard", "-z").split(b"\0")
    if include_ignored:
        paths += git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").split(b"\0")
    result = {}
    for raw in paths:
        if not raw:
            continue
        name = raw.decode("utf-8")
        p = repo / name
        if p.is_symlink():
            result[name] = "symlink:" + os.readlink(p)
        elif p.is_file():
            result[name] = hash_file(p) + ":" + str(p.stat().st_mode & 0o111)
    return result


def changed(before, after):
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))


def audit(repo, c, before, head, index):
    after = snapshot(repo, include_ignored=True)
    paths = changed(before, after)
    require(git(repo, "rev-parse", "HEAD") == head, "Worker changed Git HEAD")
    require(git(repo, "diff", "--cached", "--binary") == index, "Worker changed Git index")
    for p in paths:
        relative(p)
        require(any(contains(s, p) for s in c["scope"]), f"Out-of-scope modification: {p}")
        require(not (repo / p).is_symlink(), "Symlink changes cannot be exported")
    for p in c.get("verifier_paths", []):
        require(before.get(p) == after.get(p), "Trusted verifier was modified")
    return paths


def verify(repo, verifiers):
    repo = resolved(repo)
    results = []
    for v in verifiers:
        argv = [sys.executable if a == "{python}" else a for a in v["argv"]]
        cwd = (repo / v.get("cwd", ".")).resolve()
        require(cwd.is_relative_to(repo) and cwd.is_dir(), "Verifier cwd escapes repository or does not exist")
        r = command(argv, cwd, timeout=v.get("timeout_seconds", 120))
        r["passed"] = r["kind"] == "completed" and r["exit_code"] == 0
        pattern = v.get("implementation_failure_pattern")
        r["implementation_failure"] = bool(r["kind"] == "completed" and r["exit_code"] is not None and r["exit_code"] > 0 and pattern and re.search(pattern, r["output"]) and not INFRA.search(r["output"]))
        results.append(r)
    return results


def all_pass(results):
    return all(r["passed"] for r in results)


def resolve_models(force_online=False):
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    require(key, "DeepSeek API key is unavailable")
    base_url = os.environ.get("DEEPSEEK_BASE_URL")
    cached = None if force_online else load_capabilities(runtime_dir(), base_url=base_url)
    if cached:
        return cached["selected"]
    models = discover_models(key, base_url=base_url)
    saved = save_capabilities(runtime_dir(), models, base_url=base_url)
    require(saved["selected"].get("flash"), "DeepSeek model list does not expose a supported Flash model")
    return saved["selected"]


def sdk_attempt(repo, c, run_dir, model, feedback):
    request = dict(contract=c, workdir=str(repo), model=model, home=str(run_dir / "home"), feedback=feedback)
    write_json(run_dir / "request.json", request)
    result_file = run_dir / "worker-result.json"
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    require(key, "DeepSeek API key is unavailable")
    with BoundedCredentialProxy(
        key, model, base_url=os.environ.get("DEEPSEEK_BASE_URL"),
        max_requests=c["max_provider_requests"], max_tokens=c["max_model_output_tokens"],
        timeout=c.get("task_timeout_seconds", 600),
    ) as proxy:
        env = clean_env()
        env["DEEPSEEK_API_KEY"] = proxy.token
        env["DEEPSEEK_BASE_URL"] = proxy.base_url
        r = command([sys.executable, str(Path(__file__).with_name("sdk_worker.py")), "--request", str(run_dir / "request.json"), "--result", str(result_file)], repo, timeout=c.get("task_timeout_seconds", 600) + 40, env=env)
        proxy_info = dict(credential_proxy=True, provider_requests=proxy.request_count, provider_errors=proxy.error_count)
    if r["kind"] != "completed" or r["exit_code"] != 0 or not result_file.exists():
        return dict(finish_reason=r["kind"] if r["kind"] != "completed" else "infrastructure", diagnostic=r["output"], **proxy_info)
    result = read_json(result_file)
    result.update(proxy_info)
    return result


def export_patch(repo, head, paths, target, max_patch_bytes):
    if not paths:
        Path(target).write_bytes(b"")
        return
    with tempfile.TemporaryDirectory(prefix="router-index-") as td:
        env = clean_env()
        env["GIT_INDEX_FILE"] = str(Path(td) / "index")
        git(repo, "read-tree", head.decode().strip(), env=env)
        git(repo, "--literal-pathspecs", "add", "-A", "--", *paths, env=env)
        data = git(repo, "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", head.decode().strip(), env=env)
        require(len(data) <= max_patch_bytes, "Patch exceeds max_patch_bytes")
        require(not SECRET.search(data.decode("utf-8", errors="replace")), "Possible credential in patch; keep local for review and do not export")
        for key, value in os.environ.items():
            if len(value) >= 8 and re.search(r"KEY|TOKEN|SECRET|PASSWORD", key, re.I):
                require(value.encode() not in data, "Environment credential found in patch")
        Path(target).write_bytes(data)


def route(repo, contract, run_dir, attempt=None):
    """Caller owns the lock. attempt injection is for offline unit tests only."""
    repo = resolved(repo)
    c = validate_contract(contract)
    clean(repo, reject_ignored=True)
    run_dir = outside(repo, run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    result = dict(version=VERSION, id=c["id"], status="blocked", attempts=[], patch=None)
    try:
        before = snapshot(repo, include_ignored=True)
        require(not any(SENSITIVE.search(p) for p in before), "Repository tracks or exposes a sensitive filename; review and isolate the input first")
        require(not any(v.startswith("symlink:") for v in before.values()), "Symlink repositories need an independently isolated environment")
        for p in c.get("verifier_paths", []):
            require(p in before, "Trusted verifier path does not exist")
        head, index = git(repo, "rev-parse", "HEAD"), git(repo, "diff", "--cached", "--binary")
        baseline = verify(repo, c["preflight_verifiers"])
        result["baseline"] = baseline
        require(snapshot(repo, include_ignored=True) == before, "Baseline verifier modified repository files")
        require(git(repo, "rev-parse", "HEAD") == head and git(repo, "diff", "--cached", "--binary") == index, "Baseline verifier modified Git state")
        require(all_pass(baseline), "Preflight verification failed; fix or classify the existing failure in Codex before delegation")
        models = {"flash": "deepseek-flash", "pro": "deepseek-v4-pro"} if attempt else resolve_models()
        feedback = ""
        policy = c["model_policy"]
        if policy == "auto":
            # Codex supplies the bounded task score; harder/context-heavy work goes straight to Pro.
            policy = "pro-only" if c.get("routing_score", 0) >= 9 else "flash-first"
        sequence = (("pro", models.get("pro")),) if policy == "pro-only" else (("flash", models.get("flash")), ("pro", models.get("pro")))
        for number, (label, model) in enumerate(sequence):
            if not model:
                result.update(status="verification_failed", reason="A supported Pro model is unavailable for the permitted escalation")
                break
            attempt_dir = run_dir / label
            attempt_dir.mkdir()
            worker = (attempt or sdk_attempt)(repo, c, attempt_dir, model, feedback)
            record = dict(model=model, worker=worker)
            result["attempts"].append(record)
            paths = audit(repo, c, before, head, index)
            require(len(paths) <= c["max_changed_files"], "Candidate exceeds max_changed_files")
            changed_bytes = sum((repo / p).stat().st_size for p in paths if (repo / p).is_file())
            require(changed_bytes <= c["max_changed_bytes"], "Candidate exceeds max_changed_bytes")
            require(worker.get("finish_reason") == "completed", "Worker did not complete normally; no model escalation")
            if not paths and not c["allow_noop"]:
                result.update(status="no_changes", changed_files=[], reason="Worker completed without a reviewable change; set allow_noop only for explicitly observational tasks")
                break
            candidate = snapshot(repo, include_ignored=True)
            checks = verify(repo, c["acceptance_verifiers"])
            record["verification"] = checks
            # Verification commands must not change the candidate being evaluated.
            audit(repo, c, before, head, index)
            require(candidate == snapshot(repo, include_ignored=True), "Verifier changed candidate files")
            if all_pass(checks):
                target = run_dir / "result.patch"
                export_patch(repo, head, paths, target, c["max_patch_bytes"])
                result.update(status="passed", changed_files=paths, changed_bytes=changed_bytes, base_commit=head.decode().strip(), patch=str(target), patch_sha256=hash_file(target))
                break
            failed = [r for r in checks if not r["passed"]]
            if c["model_policy"] == "pro-only" or number or not c.get("allow_pro", False) or not all(r["implementation_failure"] for r in failed):
                result.update(status="verification_failed", reason="Failed verification; escalation is disabled or not supported by implementation-failure evidence")
                break
            feedback = "Host verification failed:\n" + "\n".join(r["output"][-8000:] for r in failed)
    except (RouterError, OSError, subprocess.SubprocessError) as exc:
        result["reason"] = redact(str(exc))
    write_json(run_dir / "route-result.json", result)
    return result
