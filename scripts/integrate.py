import argparse
import hashlib
import json
from pathlib import Path
from routerlib import clean, git, lock, read_json, require, root


def integrate(repo, patches, apply=False):
    clean(repo)
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    files, paths = set(), []
    for patch in patches:
        patch = Path(patch).resolve()
        r = read_json(patch.parent / "route-result.json")
        require(r["status"] == "passed" and r["base_commit"] == head, "Patch was not verified against the current HEAD")
        require(hashlib.sha256(patch.read_bytes()).hexdigest() == r["patch_sha256"], "Patch changed since verification; re-review and regenerate it")
        names = set(p.casefold() for p in r["changed_files"])
        require(not names.intersection(files), "Overlapping patches require deliberate conflict resolution in Codex")
        files |= names
        if patch.stat().st_size:
            paths.append(str(patch))
    if paths:
        # One git apply invocation: no --reject, no partial per-patch application.
        git(repo, "apply", "--check", "--", *paths)
        if apply:
            git(repo, "apply", "--", *paths)
    return dict(status="applied" if apply else "checked", patch_count=len(patches), changed_files=sorted(files))


def main():
    p = argparse.ArgumentParser(description="Check or explicitly apply Codex-reviewed router patches")
    p.add_argument("--workdir", required=True)
    p.add_argument("--patch", action="append", required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    a = p.parse_args()
    repo = root(a.workdir)
    with lock(repo):
        print(json.dumps(integrate(repo, a.patch, a.apply), indent=2))


if __name__ == "__main__":
    main()
