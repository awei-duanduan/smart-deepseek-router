"""Run one bounded worker through the local Claude Code Anthropic-compatible CLI."""
import argparse
import json
import os
import subprocess
from pathlib import Path

from routerlib import read_json, write_json


def run_request(request):
    c = request["contract"]
    private_root = Path(request["private_root"])
    config_dir = private_root / "claude-config"
    isolated_home = private_root / "claude-home"
    appdata = private_root / "appdata"
    local_appdata = private_root / "local-appdata"
    for directory in (config_dir, isolated_home, appdata, local_appdata):
        directory.mkdir(parents=True, exist_ok=True)
    settings_path = config_dir / "settings.json"
    settings_path.write_text(json.dumps({"permissions": {"defaultMode": "bypassPermissions"}}), encoding="utf-8")
    prompt = (
        "You are implementing one bounded task for a Codex reviewer. Read applicable AGENTS.md. "
        "Only modify the contract write scope. Do not change Git HEAD/index, commit, stage, "
        "install dependencies, access credentials or unrelated paths, deploy, or perform external mutations. "
        "Do not change trusted verifier files. If blocked, stop and explain. The host will independently verify changes.\n"
        "Contract:\n" + __import__("json").dumps(c, ensure_ascii=False) + "\n" + request.get("feedback", "")
    )
    model = request["model"]
    env = dict(os.environ)
    proxy_token = os.environ["ANTHROPIC_API_KEY"]
    env.pop("ANTHROPIC_API_KEY", None)
    env["ANTHROPIC_AUTH_TOKEN"] = proxy_token
    env["ANTHROPIC_BASE_URL"] = os.environ["ANTHROPIC_BASE_URL"]
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    env["HOME"] = str(isolated_home)
    env["USERPROFILE"] = str(isolated_home)
    env["APPDATA"] = str(appdata)
    env["LOCALAPPDATA"] = str(local_appdata)
    argv = [
        request.get("claude", "claude"), "--bare", "--print", "--no-session-persistence",
        "--settings", str(settings_path), "--disable-slash-commands", "--no-chrome",
        "--model", model, "--effort", "max", "--permission-mode", "bypassPermissions",
        "--output-format", "json", "--tools=Bash,Read,Edit,Write", prompt,
    ]
    completed = subprocess.run(argv, cwd=request["workdir"], env=env, capture_output=True, text=True,
                               timeout=c.get("task_timeout_seconds", 600) + 30)
    if completed.returncode != 0:
        detail = (completed.stderr + "\n" + completed.stdout).strip()
        return {"finish_reason": "error", "diagnostic": detail[-4000:]}
    return {
        "finish_reason": "completed", "diagnostic": "", "cli_output": completed.stdout[-4000:],
        "isolated_config": True,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--result", required=True)
    args = p.parse_args()
    try:
        result = run_request(read_json(args.request))
    except subprocess.TimeoutExpired:
        result = {"finish_reason": "timeout", "diagnostic": "Claude Code worker timed out"}
    except Exception as exc:
        result = {"finish_reason": "infrastructure", "diagnostic": type(exc).__name__}
    write_json(args.result, result)


if __name__ == "__main__":
    main()
