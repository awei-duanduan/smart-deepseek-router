import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import orchestrate


class RegressionTests(unittest.TestCase):
    def test_parallel_tasks_get_distinct_worktrees(self):
        with tempfile.TemporaryDirectory() as td:
            base, repo = Path(td), Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "baseline"], cwd=repo, check=True)
            def runner(task, child_repo, run_dir):
                child_dir = child_repo
                self.assertTrue(child_dir.is_dir())
                return {"id": task["id"], "model": task["model"], "status": "passed", "worktree": str(child_dir)}
            contracts = [
                {"schema_version": 2, "id": "a", "objective": "x", "scope": ["a.txt"], "acceptance": ["x"], "acceptance_verifiers": [{"argv": ["python", "-c", "pass"]}]},
                {"schema_version": 2, "id": "b", "objective": "x", "scope": ["b.txt"], "acceptance": ["x"], "acceptance_verifiers": [{"argv": ["python", "-c", "pass"]}]},
            ]
            tasks = [{"id": "a", "model": "flash", "contract": contracts[0]}, {"id": "b", "model": "pro", "contract": contracts[1]}]
            result = orchestrate.run_parallel(tasks, base / "run", repo=repo, runner=runner, max_workers=2)
            self.assertEqual(result["status"], "passed")
            self.assertNotEqual(result["tasks"][0]["worktree"], result["tasks"][1]["worktree"])

    def test_codex_model_is_directly_assigned(self):
        self.assertEqual(orchestrate.select_model({"model": "sol"}), ("codex", "gpt-5.6-sol"))
        self.assertEqual(orchestrate.select_model({"model": "pro"}), ("deepseek", "deepseek-v4-pro"))

    def test_codex_runner_uses_parent_created_attempt_directory(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo, attempt = base / "repo", base / "attempt"
            repo.mkdir(); attempt.mkdir()
            contract = {"task_timeout_seconds": 30}
            fake = {"kind": "completed", "exit_code": 0, "output": ""}
            with patch.object(orchestrate.lib, "command", return_value=fake):
                result = orchestrate.run_codex({"model": "luna", "prompt": "x"}, repo, contract, attempt, "gpt-5.6-luna")
            self.assertEqual(result["finish_reason"], "infrastructure")
            self.assertTrue((attempt / "process-result.json").is_file())


if __name__ == "__main__":
    unittest.main()
