"""Create the dedicated runtime and install the verified DeepSeek Harness SDK build."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import venv

from credentials import runtime_dir


DEFAULT_VERSION = "0.1.5rc1"


def main():
    parser = argparse.ArgumentParser(description="Install Smart DeepSeek Router's dedicated Python runtime")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="deepseek-harness-sdk version")
    parser.add_argument("--runtime-dir", help="override the dedicated runtime directory")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}(?:[A-Za-z0-9.-]+)?", args.version):
        parser.error("--version must be a package version, for example 0.1.5rc1")
    target = Path(args.runtime_dir).expanduser().resolve() if args.runtime_dir else runtime_dir().resolve()
    skill = Path(__file__).resolve().parents[1]
    if target == skill or skill in target.parents:
        parser.error("The runtime must be outside the skill directory")
    executable = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not executable.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=os.name != "nt").create(target)
    requirement = "deepseek-harness-sdk==" + args.version
    subprocess.run([str(executable), "-m", "pip", "install", requirement], check=True)
    check = subprocess.run(
        [str(executable), "-c", "import importlib.metadata as m; print(m.version('deepseek-harness-sdk')); print(m.version('deepseek-harness-runtime-bin'))"],
        check=True, capture_output=True, text=True,
    )
    versions = check.stdout.strip().splitlines()
    print("Runtime:", target)
    print("deepseek-harness-sdk:", versions[0])
    print("deepseek-harness-runtime-bin:", versions[1])
    print("Next: configure DEEPSEEK_API_KEY, then run scripts/run.py doctor --online")


if __name__ == "__main__":
    main()
