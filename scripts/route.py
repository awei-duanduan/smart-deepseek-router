import argparse
import json
from pathlib import Path
from doctor import check
from routerlib import lock, outside, read_json, require, root, route, write_json


def main():
    p = argparse.ArgumentParser(description="Run one bounded contract on a clean, authorized repository")
    p.add_argument("--workdir", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--result-out")
    a = p.parse_args()
    repo = root(a.workdir)
    if a.result_out:
        outside(repo, a.result_out)
        require(not Path(a.result_out).exists(), "Result output already exists")
    require(check()["ready_for_live_attempt"], "SDK/runtime or environment credential is missing; run doctor.py; no packages are installed automatically")
    with lock(repo):
        result = route(repo, read_json(a.contract), a.run_dir)
    if a.result_out:
        write_json(a.result_out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
