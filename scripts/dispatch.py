import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

from doctor import check
from routerlib import SENSITIVE, clean, compile_plan, git, lock, outside, read_json, redact, require, root, route, snapshot, write_json


def dispatch(repo, plan, run_dir, max_workers=3, attempt=None):
    require(type(max_workers) is int and 1 <= max_workers <= 3, "max-workers must be 1..3")
    clean(repo)
    compiled = compile_plan(plan)
    candidates = {d["id"] for d in compiled["decisions"] if d["parallel_eligible"]}
    for a, b in compiled["conflicts"]:
        if a in candidates and b in candidates:
            candidates.discard(a)
            candidates.discard(b)
    # Check every selected scope pair again: a conflict involving an already
    # rejected task must never allow an overlapping selected pair through.
    selected = [c for c in compiled["contracts"] if c["id"] in candidates]
    require(selected, "No independent non-overlapping candidates; use Codex or an explicit sequential contract")
    run_dir = outside(repo, run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "routing.json", compiled)
    worktree_root = run_dir / "worktrees"
    worktree_root.mkdir()
    before, head = snapshot(repo, include_ignored=True), git(repo, "rev-parse", "HEAD")
    require(not any(SENSITIVE.search(p) for p in before), "Primary repository exposes a sensitive filename; isolate it before dispatch")
    worktrees, results = {}, []
    try:
        for c in selected:
            path = worktree_root / c["id"]
            require(path.resolve().parent == worktree_root.resolve(), "Worktree path escaped run directory")
            git(repo, "worktree", "add", "--detach", str(path), head.decode().strip())
            worktrees[c["id"]] = path
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(route, worktrees[c["id"]], c, run_dir / "tasks" / c["id"], attempt): c["id"] for c in selected}
            for f in as_completed(futures):
                task_id = futures[f]
                try:
                    r = f.result()
                except Exception as exc:
                    r = dict(id=task_id, status="blocked", reason=redact(str(exc)) or type(exc).__name__)
                results.append(r)
    finally:
        # Failed worktrees remain available for inspection; never discard them.
        for r in results:
            path = worktrees[r["id"]]
            if r["status"] == "passed":
                require(path.resolve().parent == worktree_root.resolve(), "Unsafe cleanup path")
                try:
                    git(repo, "worktree", "remove", "--force", str(path))
                except Exception as exc:
                    r["cleanup_warning"] = type(exc).__name__
                    r["retained_worktree"] = str(path)
            else:
                r["retained_worktree"] = str(path)
        untouched = snapshot(repo, include_ignored=True) == before and git(repo, "rev-parse", "HEAD") == head and not git(repo, "status", "--porcelain=v1", "--untracked-files=all")
        summary = dict(status="passed" if results and all(r["status"] == "passed" for r in results) and untouched else "needs_review", primary_unchanged=bool(untouched), tasks=sorted(results, key=lambda r: r["id"]), not_dispatched=[d["id"] for d in compiled["decisions"] if d["id"] not in candidates], worktrees={k: str(v) for k, v in worktrees.items() if v.exists()})
        write_json(run_dir / "dispatch-result.json", summary)
    return summary


def main():
    p = argparse.ArgumentParser(description="Generate reviewed-result patches in isolated Git worktrees")
    p.add_argument("--workdir", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--max-workers", type=int, default=3)
    a = p.parse_args()
    require(check()["ready_for_live_attempt"], "SDK/runtime or environment credential is missing; run doctor.py")
    repo = root(a.workdir)
    with lock(repo):
        result = dispatch(repo, read_json(a.plan), a.run_dir, a.max_workers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
