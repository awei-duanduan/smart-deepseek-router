"""Use the dedicated local runtime and load its user-encrypted key in memory."""
import argparse
import os
from pathlib import Path
import subprocess
from credentials import load_key, runtime_dir


def main():
    p = argparse.ArgumentParser(description="Run Smart DeepSeek Router with its configured local environment")
    p.add_argument("command", choices=["doctor", "plan", "route", "dispatch", "integrate", "configure"])
    args, rest = p.parse_known_args()
    directory = runtime_dir()
    executable = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not executable.is_file():
        p.error("Dedicated runtime is missing; see references/runtime.md")
    env = os.environ.copy()
    if args.command in ("doctor", "route", "dispatch") and not env.get("DEEPSEEK_API_KEY") and os.name == "nt":
        key = load_key()
        if key:
            env["DEEPSEEK_API_KEY"] = key
    return subprocess.call([str(executable), "-B", str(Path(__file__).with_name(args.command + ".py")), *rest], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
