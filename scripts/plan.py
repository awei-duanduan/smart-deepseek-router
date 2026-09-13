import argparse
import json
from routerlib import read_json, save_plan


def main():
    p = argparse.ArgumentParser(description="Validate candidates and create scored contracts without API calls")
    p.add_argument("--plan", required=True)
    p.add_argument("--out-dir", required=True)
    a = p.parse_args()
    result = save_plan(read_json(a.plan), a.out_dir)
    print(json.dumps({k: result[k] for k in ("version", "decisions", "conflicts")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
