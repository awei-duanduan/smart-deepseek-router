import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import anthropic_worker


class AnthropicWorkerTests(unittest.TestCase):
    def test_worker_isolates_user_config_and_forces_proxy_environment(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured.update(argv=argv, env=kwargs["env"])
            return type("Completed", (), {"returncode": 0, "stdout": '{"type":"result"}', "stderr": ""})()

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "temporary-proxy-token",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:54321",
        }, clear=False), patch.object(anthropic_worker.subprocess, "run", fake_run):
            request = {
                "contract": {"task_timeout_seconds": 30}, "workdir": td,
                "private_root": str(Path(td) / "private"), "model": "deepseek-v4-pro[1m]",
                "claude": "claude.exe", "feedback": "",
            }
            result = anthropic_worker.run_request(request)

        self.assertEqual(result["finish_reason"], "completed")
        self.assertTrue(result["isolated_config"])
        self.assertNotIn("ANTHROPIC_API_KEY", captured["env"])
        self.assertEqual(captured["env"]["ANTHROPIC_AUTH_TOKEN"], "temporary-proxy-token")
        self.assertEqual(captured["env"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:54321")
        self.assertIn("claude-config", captured["env"]["CLAUDE_CONFIG_DIR"])
        self.assertEqual(captured["env"]["HOME"], captured["env"]["USERPROFILE"])
        self.assertIn("--settings", captured["argv"])
        self.assertIn("--bare", captured["argv"])


if __name__ == "__main__":
    unittest.main()
