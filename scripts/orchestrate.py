"""Run Astra-assigned workers concurrently and collect reviewable results."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import routerlib as lib

CODEX_MODELS = {"luna": "gpt-5.6-luna", "terra": "gpt-5.6-terra", "sol": "gpt-5.6-sol"}
DEEPSEEK_MODELS = {"flash": "deepseek-flash", "pro": "deepseek-v4-pro"}


def select_model(task):
    name = task.get("model")
    if name in CODEX_MODELS:
        return "codex", CODEX_MODELS[name]
    if name in DEEPSEEK_MODELS:
        return "deepseek", DEEPSEEK_MODELS[name]
    raise ValueError("model must be sol, terra, luna, pro or flash")


def build_codex_argv(task, repo, run_dir):
    return ["codex", "exec", "--model", select_model(task)[1], "--cd", str(repo),
            "--approve-for-me", "--ignore-user-config", "--ephemeral",
            "--json", "--output-last-message", str(run_dir / "last-message.txt"), task["prompt"]]


def load_contract(task):
    value = task.get("contract")
    if isinstance(value, (str, Path)):
        value = lib.read_json(value)
    lib.require(isinstance(value, dict), "Each worker requires a reviewed contract")
    contract = lib.validate_contract(value)
    lib.require(contract["id"] == task["id"], "Task and contract ids must match")
    return contract


def run_codex(task, repo, contract, run_dir, model):
    # routerlib.route owns and creates the per-model attempt directory.
    lib.require(run_dir.is_dir(), "Codex attempt directory was not prepared by the parent route")
    prompt = ("Implement only this reviewed contract. Do not commit, stage, install dependencies, "
              "access credentials, deploy, or modify trusted verifiers.\n" + json.dumps(contract, ensure_ascii=False))
    source_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    auth = source_home / "auth.json"
    lib.require(auth.is_file(), "Codex authentication is unavailable")
    # Give the child only temporary authentication, not the user's config, rules,
    # plugins, or skills. The directory is deleted as soon as the worker exits.
    with tempfile.TemporaryDirectory(prefix="smart-router-codex-") as isolated:
        isolated_home = Path(isolated)
        shutil.copy2(auth, isolated_home / "auth.json")
        env = lib.clean_env()
        env["CODEX_HOME"] = str(isolated_home)
        result = lib.command(build_codex_argv(dict(task, prompt=prompt), repo, run_dir), repo,
                             timeout=contract["task_timeout_seconds"], env=env)
    lib.write_json(run_dir / "process-result.json", result)
    final = run_dir / "last-message.txt"
    completed = result["kind"] == "completed" and result["exit_code"] == 0 and final.is_file()
    return {"finish_reason": "completed" if completed else "infrastructure",
            "summary": lib.redact(final.read_text(encoding="utf-8")[:4000]) if final.is_file() else "",
            "diagnostic": result["output"] if not completed else "", "model": model}


def default_runner(task, repo, run_dir):
    contract = load_contract(task)
    kind, model = select_model(task)
    attempt = (lambda _repo, _contract, out, _model, _feedback:
               run_codex(task, _repo, _contract, out, model)) if kind == "codex" else None
    result = lib.route(repo, contract, run_dir, attempt=attempt, assigned_model=model)
    result.update(model=model, run_dir=str(run_dir))
    return result


def run_parallel(tasks, run_dir, repo=None, max_workers=3, runner=None):
    lib.require(isinstance(tasks, list) and 1 <= len(tasks) <= 32, "Expected 1..32 tasks")
    lib.require(type(max_workers) is int and 1 <= max_workers <= 5, "max-workers must be 1..5")
    ids, contracts = set(), []
    for task in tasks:
        lib.require(isinstance(task, dict) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", task.get("id", "")), "Invalid task id")
        lib.require(task["id"] not in ids, "Duplicate task id")
        lib.require(not task.get("depends_on") and not task.get("blockers"), "Resolve dependencies/blockers before dispatch")
        select_model(task)
        ids.add(task["id"])
        contracts.append(load_contract(task))
    for i, left in enumerate(contracts):
        for right in contracts[i + 1:]:
            lib.require(not any(lib.overlap(a, b) for a in left["scope"] for b in right["scope"]), "Overlapping task scopes")
    repo = lib.root(repo)
    run_dir = lib.outside(repo, run_dir)
    with lib.lock(repo):
        lib.clean(repo)
        before = lib.snapshot(repo, include_ignored=True)
        lib.require(not any(lib.SENSITIVE.search(p) for p in before), "Sensitive repository input")
        head = lib.git(repo, "rev-parse", "HEAD")
        run_dir.mkdir(parents=True, exist_ok=False)
        worktree_root = run_dir / "worktrees"
        worktrees, results = {}, []
        try:
            for task in tasks:
                path = worktree_root / task["id"]
                lib.git(repo, "worktree", "add", "--detach", str(path), head.decode().strip())
                worktrees[task["id"]] = path
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(runner or default_runner, task, worktrees[task["id"]],
                                       run_dir / "tasks" / task["id"]): task for task in tasks}
                for future in as_completed(futures):
                    task = futures[future]
                    try:
                        results.append(future.result())
                    except Exception as exc:
                        results.append({"id": task["id"], "model": task["model"], "status": "blocked",
                                        "reason": lib.redact(str(exc))})
            untouched = lib.snapshot(repo, include_ignored=True) == before and lib.git(repo, "rev-parse", "HEAD") == head and not lib.git(repo, "status", "--porcelain=v1", "--untracked-files=all")
            status = "passed" if untouched and all(r["status"] == "passed" for r in results) else "needs_review"
            summary = {"status": status, "parallel": True, "primary_unchanged": bool(untouched),
                       "tasks": sorted(results, key=lambda r: r["id"]), "run_dir": str(run_dir),
                       "worktrees": {k: str(v) for k, v in worktrees.items()}}
            lib.write_json(run_dir / "orchestration-result.json", summary)
            return summary
        except Exception:
            lib.write_json(run_dir / "orchestration-result.json", {"status": "needs_review", "worktrees": {k: str(v) for k, v in worktrees.items()}, "tasks": results})
            raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--max-workers", type=int, default=3)
    args = p.parse_args()
    plan_path = Path(args.plan).resolve()
    plan = lib.read_json(plan_path)
    tasks = plan["tasks"]
    for task in tasks:
        if isinstance(task.get("contract"), str):
            task["contract"] = str((plan_path.parent / task["contract"]).resolve())
    result = run_parallel(tasks, args.run_dir, args.repo, args.max_workers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
