import tempfile
import unittest
from pathlib import Path
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from orchestrate import build_codex_argv, select_model, run_parallel


class OrchestrateTests(unittest.TestCase):
    def test_select_model_is_direct_not_escalating(self):
        self.assertEqual(select_model({"model": "flash"}), ("deepseek", "deepseek-flash"))
        self.assertEqual(select_model({"model": "pro"}), ("deepseek", "deepseek-v4-pro"))
        self.assertEqual(select_model({"model": "luna"}), ("codex", "gpt-5.6-luna"))
        self.assertEqual(select_model({"model": "terra"}), ("codex", "gpt-5.6-terra"))
        self.assertEqual(select_model({"model": "sol"}), ("codex", "gpt-5.6-sol"))

    def test_codex_command_keeps_task_isolated(self):
        argv = build_codex_argv({"prompt": "inspect files", "model": "terra"}, Path("C:/repo"), Path("C:/run"))
        self.assertEqual(argv[:4], ["codex", "exec", "--model", "gpt-5.6-terra"])
        self.assertIn("--json", argv)
        self.assertIn("--ephemeral", argv)
        self.assertIn("--approve-for-me", argv)
        self.assertNotIn("--ask-for-approval", argv)
        self.assertNotIn("--sandbox", argv)

    def test_parallel_runner_collects_all_results(self):
        def fake_runner(task, child_repo, run_dir):
            return {"id": task["id"], "status": "passed", "model": task["model"], "run_dir": str(run_dir)}

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "baseline"], cwd=repo, check=True)
            contract = {"schema_version": 2, "id": "a", "objective": "x", "scope": ["a.txt"], "acceptance": ["x"], "acceptance_verifiers": [{"argv": ["python", "-c", "pass"]}]}
            contract_b = dict(contract, id="b", scope=["b.txt"])
            tasks = [{"id": "a", "model": "flash", "contract": contract}, {"id": "b", "model": "sol", "prompt": "x", "contract": contract_b}]
            result = run_parallel(tasks, Path(td) / "run", repo=repo, runner=fake_runner, max_workers=2)
        self.assertEqual(result["status"], "passed")
        self.assertEqual([x["id"] for x in result["tasks"]], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
