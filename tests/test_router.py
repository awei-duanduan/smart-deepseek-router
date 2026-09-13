"""Offline behavior tests. Uses disposable real Git repositories, never an API."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import routerlib as lib
from provider_proxy import BoundedCredentialProxy, select_models
from dispatch import dispatch
from integrate import integrate
from sdk_worker import run_request


def contract(task="one", scope=None):
    return dict(schema_version=2, id=task, objective="Update the selected text file", scope=scope or ["a.txt"], acceptance=["Files remain readable"], preflight_verifiers=[], acceptance_verifiers=[dict(argv=["{python}", "-c", "from pathlib import Path; assert Path('a.txt').is_file()"], timeout_seconds=10)], allow_pro=False)


def task(c):
    c = copy.deepcopy(c)
    c.pop("schema_version")
    c.update(traits=dict(bounded=True, verifiable=True, independent=True, dependency_stable=True, repetitive=False, context_heavy=False), blockers=[], depends_on=[])
    return c


class RepoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="router-test-")
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        lib.git(self.repo, "init", "-q")
        lib.git(self.repo, "config", "user.name", "Router test")
        lib.git(self.repo, "config", "user.email", "router@example.invalid")
        for name in ("a.txt", "b.txt", "trusted.py"):
            (self.repo / name).write_text("old\n")
        lib.git(self.repo, "add", ".")
        lib.git(self.repo, "commit", "-qm", "baseline")

    def tearDown(self):
        # Git files can be read-only on Windows; clear only our generated temp tree.
        def onerror(func, path, exc):
            os.chmod(path, 0o700)
            func(path)
        import shutil
        shutil.rmtree(self.base, onerror=onerror)
        self.temp.cleanup()

    def route(self, c, attempt):
        return lib.route(self.repo, c, self.base / "run", attempt=attempt)

    def test_passing_patch_preserves_index_and_new_binary(self):
        def worker(repo, *args):
            (repo / "a.txt").write_text("new\n")
            (repo / "new.bin").write_bytes(bytes(range(256)))
            return {"finish_reason": "completed"}
        r = self.route(contract(scope=["a.txt", "new.bin"]), worker)
        self.assertEqual(r["status"], "passed", r)
        self.assertEqual(set(r["changed_files"]), {"a.txt", "new.bin"})
        self.assertFalse(lib.git(self.repo, "diff", "--cached"))
        # Reset only generated fixture files, then apply exported binary patch.
        (self.repo / "a.txt").write_text("old\n")
        (self.repo / "new.bin").unlink()
        integrate(self.repo, [r["patch"]], False)
        self.assertEqual((self.repo / "a.txt").read_text(), "old\n")
        integrate(self.repo, [r["patch"]], True)
        self.assertEqual((self.repo / "new.bin").read_bytes(), bytes(range(256)))

    def test_out_of_scope_stops_without_escalation(self):
        calls = []
        def worker(repo, c, rd, model, feedback):
            calls.append(model)
            (repo / "b.txt").write_text("unauthorized\n")
            return {"finish_reason": "completed"}
        c = contract(); c["allow_pro"] = True
        r = self.route(c, worker)
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(len(calls), 1)
        self.assertFalse((self.base / "run/result.patch").exists())

    def test_baseline_failure_never_dispatches(self):
        c = contract()
        c["preflight_verifiers"] = [dict(argv=["{python}", "-c", "raise AssertionError('baseline')"])]
        def worker(*args):
            self.fail("Worker must not run")
        self.assertEqual(self.route(c, worker)["status"], "blocked")

    def test_escalates_once_for_host_assertion(self):
        c = contract(); c["allow_pro"] = True
        c["acceptance_verifiers"][0].update(argv=["{python}", "-c", "from pathlib import Path; assert Path('a.txt').read_text().strip() != 'bad'"], implementation_failure_pattern="AssertionError")
        calls = []
        def worker(repo, c, rd, model, feedback):
            calls.append(model)
            (repo / "a.txt").write_text("bad" if len(calls) == 1 else "fixed")
            return {"finish_reason": "completed"}
        r = self.route(c, worker)
        self.assertEqual(r["status"], "passed", r)
        self.assertEqual(calls, ["deepseek-flash", "deepseek-v4-pro"])

    def test_dependency_error_never_escalates(self):
        c = contract(); c["allow_pro"] = True
        c["acceptance_verifiers"][0].update(argv=["{python}", "-c", "from pathlib import Path; exec('raise ModuleNotFoundError(\"AssertionError\")') if Path('a.txt').read_text() == 'bad' else None"], implementation_failure_pattern="AssertionError")
        def worker(repo, *args):
            (repo / "a.txt").write_text("bad")
            return {"finish_reason": "completed"}
        r = self.route(c, worker)
        self.assertEqual(r["status"], "verification_failed")
        self.assertEqual(len(r["attempts"]), 1)

    def test_worker_limit_never_escalates(self):
        c = contract(); c["allow_pro"] = True
        r = self.route(c, lambda *args: {"finish_reason": "max-tokens"})
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(len(r["attempts"]), 1)

    def test_no_failure_pattern_never_escalates(self):
        c = contract(); c["allow_pro"] = True
        c["acceptance_verifiers"][0]["argv"] = ["{python}", "-c", "from pathlib import Path; assert Path('a.txt').read_text() != 'bad'"]
        def worker(repo, *args):
            (repo / "a.txt").write_text("bad")
            return {"finish_reason": "completed"}
        r = self.route(c, worker)
        self.assertEqual(len(r["attempts"]), 1)

    def test_verifier_cannot_mutate_same_candidate_file(self):
        c = contract()
        c["acceptance_verifiers"][0]["argv"] = ["{python}", "-c", "from pathlib import Path; p=Path('a.txt'); p.write_text('rewritten') if p.read_text() == 'candidate' else None"]
        def worker(repo, *args):
            (repo / "a.txt").write_text("candidate")
            return {"finish_reason": "completed"}
        self.assertEqual(self.route(c, worker)["status"], "blocked")

    def test_dirty_repository_unchanged(self):
        (self.repo / "b.txt").write_text("user work")
        with self.assertRaises(lib.RouterError):
            self.route(contract(), lambda *a: self.fail())
        self.assertEqual((self.repo / "b.txt").read_text(), "user work")

    def test_ignored_user_files_prevent_direct_execution(self):
        (self.repo / ".gitignore").write_text("private-notes.txt\n")
        lib.git(self.repo, "add", ".gitignore")
        lib.git(self.repo, "commit", "-qm", "ignore private notes")
        (self.repo / "private-notes.txt").write_text("keep me")
        with self.assertRaises(lib.RouterError):
            self.route(contract(), lambda *a: self.fail("Ignored user file must block before execution"))
        self.assertEqual((self.repo / "private-notes.txt").read_text(), "keep me")

    def test_worker_new_ignored_file_is_audited(self):
        (self.repo / ".gitignore").write_text("ignored.txt\n")
        lib.git(self.repo, "add", ".gitignore")
        lib.git(self.repo, "commit", "-qm", "ignore generated file")
        def worker(repo, *args):
            (repo / "ignored.txt").write_text("outside scope")
            return {"finish_reason": "completed"}
        self.assertEqual(self.route(contract(), worker)["status"], "blocked")

    def test_worker_staging_is_rejected(self):
        def worker(repo, *args):
            (repo / "a.txt").write_text("new")
            lib.git(repo, "add", "a.txt")
            return {"finish_reason": "completed"}
        self.assertEqual(self.route(contract(), worker)["status"], "blocked")

    def test_tampered_patch_rejected(self):
        def worker(repo, *args):
            (repo / "a.txt").write_text("changed")
            return {"finish_reason": "completed"}
        r = self.route(contract(), worker)
        Path(r["patch"]).write_text("tampered")
        with self.assertRaises(lib.RouterError):
            integrate(self.repo, [r["patch"]])

    def test_noop_is_rejected_by_default(self):
        r = self.route(contract(), lambda *a: {"finish_reason": "completed"})
        self.assertEqual(r["status"], "no_changes", r)
        self.assertIsNone(r["patch"])

    def test_acceptance_may_require_worker_change(self):
        c = contract()
        c["acceptance_verifiers"][0]["argv"] = ["{python}", "-c", "from pathlib import Path; assert Path('a.txt').read_text() == 'implemented'"]
        def worker(repo, *args):
            (repo / "a.txt").write_text("implemented")
            return {"finish_reason": "completed"}
        self.assertEqual(self.route(c, worker)["status"], "passed")

    def test_change_size_limit_blocks_export(self):
        c = contract(); c["max_changed_bytes"] = 3
        def worker(repo, *args):
            (repo / "a.txt").write_text("too large")
            return {"finish_reason": "completed"}
        self.assertEqual(self.route(c, worker)["status"], "blocked")

    def test_parallel_primary_untouched_and_patch_batch_applies(self):
        p = dict(schema_version=2, tasks=[task(contract()), task(contract("two", ["b.txt"]))])
        def worker(repo, c, *args):
            (repo / c["scope"][0]).write_text(c["id"])
            return {"finish_reason": "completed"}
        with lib.lock(self.repo):
            r = dispatch(self.repo, p, self.base / "parallel", attempt=worker)
        self.assertEqual(r["status"], "passed", r)
        self.assertTrue(r["primary_unchanged"])
        self.assertEqual((self.repo / "a.txt").read_text(), "old\n")
        patches = [t["patch"] for t in r["tasks"]]
        integrate(self.repo, patches, True)
        self.assertEqual((self.repo / "a.txt").read_text(), "one")
        self.assertEqual((self.repo / "b.txt").read_text(), "two")

    def test_parallel_failure_retains_worktree(self):
        p = dict(schema_version=2, tasks=[task(contract())])
        def worker(repo, *args):
            (repo / "b.txt").write_text("out of scope")
            return {"finish_reason": "completed"}
        r = dispatch(self.repo, p, self.base / "parallel", attempt=worker)
        self.assertEqual(r["status"], "needs_review")
        self.assertTrue(Path(r["tasks"][0]["retained_worktree"]).exists())
        self.assertTrue(r["primary_unchanged"])

    def test_parallel_detects_primary_ignored_file_mutation(self):
        (self.repo / ".gitignore").write_text("cache.tmp\n")
        lib.git(self.repo, "add", ".gitignore")
        lib.git(self.repo, "commit", "-qm", "ignore cache")
        ignored = self.repo / "cache.tmp"
        ignored.write_text("before")
        p = dict(schema_version=2, tasks=[task(contract())])
        def worker(repo, *args):
            (repo / "a.txt").write_text("candidate")
            ignored.write_text("tampered")
            return {"finish_reason": "completed"}
        r = dispatch(self.repo, p, self.base / "parallel", attempt=worker)
        self.assertEqual(r["status"], "needs_review")
        self.assertFalse(r["primary_unchanged"])

    def test_lock_excludes_second_run(self):
        with lib.lock(self.repo):
            with self.assertRaises(lib.RouterError):
                with lib.lock(self.repo):
                    pass


class PureTests(unittest.TestCase):
    def test_blockers_keep_task_in_codex(self):
        t = task(contract()); t["blockers"] = ["deployment"]
        p = lib.compile_plan(dict(schema_version=2, tasks=[t]))
        self.assertEqual(p["contracts"], [])

    def test_path_traversal_drive_glob_and_secret_rejected(self):
        for scope in ("../x", "C:/x", "/x", "src/*.py", ".env", "src/../../x", "src\\x"):
            with self.subTest(scope=scope), self.assertRaises(lib.RouterError):
                lib.validate_contract(contract(scope=[scope]))

    def test_portable_scope_overlap(self):
        p = lib.compile_plan(dict(schema_version=2, tasks=[task(contract(scope=["Src/"])), task(contract("two", ["src/a.py"]))]))
        self.assertEqual(p["conflicts"], [["one", "two"]])
        self.assertFalse(lib.overlap("src/", "src2/a.py"))
        self.assertTrue(lib.overlap("Src/", "src/"))

    def test_same_directory_scopes_are_not_dispatched(self):
        p = lib.compile_plan(dict(schema_version=2, tasks=[task(contract(scope=["src/"])), task(contract("two", ["src/"]))]))
        self.assertEqual(p["conflicts"], [["one", "two"]])

    def test_missing_traits_not_guessed(self):
        t = task(contract()); del t["traits"]["bounded"]
        with self.assertRaises(lib.RouterError):
            lib.compile_plan(dict(schema_version=2, tasks=[t]))

    def test_verifier_paths_cannot_be_writable(self):
        c = contract(); c["verifier_paths"] = ["a.txt"]
        with self.assertRaises(lib.RouterError):
            lib.validate_contract(c)

    def test_unknown_contract_field_is_rejected(self):
        c = contract(); c["allowPro"] = True
        with self.assertRaises(lib.RouterError):
            lib.validate_contract(c)

    def test_dependency_cycle_is_rejected(self):
        first, second = task(contract()), task(contract("two", ["b.txt"]))
        first["depends_on"], second["depends_on"] = ["two"], ["one"]
        with self.assertRaises(lib.RouterError):
            lib.compile_plan(dict(schema_version=2, tasks=[first, second]))

    def test_model_selection_uses_discovered_names(self):
        self.assertEqual(select_models(["deepseek-v4-flash", "deepseek-v4-pro"]), {"flash": "deepseek-v4-flash", "pro": "deepseek-v4-pro"})

    def test_proxy_hides_key_forces_model_and_caps_requests(self):
        observed = {}
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                observed.update(json.loads(self.rfile.read(length)))
                observed["authorization"] = self.headers.get("Authorization")
                body = b'{"ok":true}'
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        server = HTTPServer(("127.0.0.1", 0), Upstream)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with BoundedCredentialProxy("real-secret-key", "deepseek-v4-pro", base_url=f"http://127.0.0.1:{server.server_port}", max_requests=1, max_tokens=99) as proxy:
                def call():
                    request = urllib.request.Request(proxy.base_url + "/chat/completions", data=json.dumps({"model": "wrong", "max_tokens": 1000}).encode(), headers={"Authorization": "Bearer " + proxy.token, "Content-Type": "application/json"})
                    return urllib.request.urlopen(request, timeout=5).read()
                self.assertEqual(call(), b'{"ok":true}')
                with self.assertRaises(urllib.error.HTTPError) as limited:
                    call()
                self.assertEqual(limited.exception.code, 429)
                limited.exception.close()
                self.assertNotEqual(proxy.token, "real-secret-key")
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        self.assertEqual(observed["authorization"], "Bearer real-secret-key")
        self.assertEqual(observed["model"], "deepseek-v4-pro")
        self.assertEqual(observed["max_tokens"], 99)

    def test_process_timeout(self):
        r = lib.command([sys.executable, "-c", "import time; time.sleep(10)"], Path.cwd(), timeout=0.1)
        self.assertEqual(r["kind"], "timeout")

    def test_sdk_adapter_uses_real_public_field_names(self):
        record = {}
        class FakeHarness:
            def __init__(self, **kw): record.update(kw)
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def run(self, prompt, session_id):
                record["session_id"] = session_id
                return type("Result", (), {"finish_reason": "completed"})()
        r = run_request(dict(contract=contract(), workdir="/tmp/repo", home="/tmp/home", model="deepseek-flash"), FakeHarness)
        self.assertEqual(record["profile"], "sdk-minimal")
        self.assertEqual(record["request_timeout_seconds"], 600)
        self.assertEqual(r, {"finish_reason": "completed"})


if __name__ == "__main__":
    unittest.main()
