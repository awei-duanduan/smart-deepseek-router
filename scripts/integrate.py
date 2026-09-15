import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from routerlib import (clean, create_git_mirror, directory_snapshot, git, is_git_root,
                       lock, read_json, relative, require, resolved, root)


def verified_patch_metadata(patches):
    files, paths, results = set(), [], []
    for patch_value in patches:
        patch = resolved(patch_value)
        result = read_json(patch.parent / "route-result.json")
        require(result["status"] == "passed", "Patch was not produced by a passed router task")
        require(hashlib.sha256(patch.read_bytes()).hexdigest() == result["patch_sha256"],
                "Patch changed since verification; re-review and regenerate it")
        names = {relative(name).casefold() for name in result["changed_files"]}
        require(not names.intersection(files), "Overlapping patches require deliberate conflict resolution in Codex")
        files |= names
        results.append((patch, result))
        if patch.stat().st_size:
            paths.append(str(patch))
    return files, paths, results


def integrate_git(repo, patches, apply=False):
    clean(repo)
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    files, paths, results = verified_patch_metadata(patches)
    require(all(result["base_commit"] == head for _, result in results),
            "Patch was not verified against the current HEAD")
    if paths:
        git(repo, "apply", "--check", "--", *paths)
        if apply:
            git(repo, "apply", "--", *paths)
    return dict(status="applied" if apply else "checked", source_mode="git",
                patch_count=len(patches), changed_files=sorted(files))


def integrate_plain(source, patches, apply=False):
    files, paths, results = verified_patch_metadata(patches)
    manifests = []
    for patch, result in results:
        require(result.get("source_mode") == "temporary-git-mirror",
                "Plain-directory integration requires a temporary-mirror result")
        manifest_path = patch.parent / "source-manifest.json"
        require(manifest_path.is_file(), "Source manifest is missing beside the patch")
        manifest = read_json(manifest_path)
        require(resolved(manifest["source_root"]) == source, "Patch belongs to a different source directory")
        require(result["base_commit"] == manifest["base_commit"], "Patch and source manifest baselines differ")
        manifests.append(manifest)
    require(manifests and all(m["files"] == manifests[0]["files"] and m["base_commit"] == manifests[0]["base_commit"] for m in manifests),
            "Patches were created from different source snapshots")
    baseline = manifests[0]
    require(directory_snapshot(source, mirrorable_only=True)["files"] == baseline["files"],
            "Source changed after dispatch; regenerate patches from the current directory")

    with tempfile.TemporaryDirectory(prefix="router-integrate-") as temp_name:
        candidate = Path(temp_name) / "candidate"
        created = create_git_mirror(source, candidate)
        require(created["files"] == baseline["files"], "Source changed while preparing integration")
        if paths:
            git(candidate, "apply", "--check", "--", *paths)
            git(candidate, "apply", "--", *paths)
        if not apply:
            return dict(status="checked", source_mode="temporary-git-mirror",
                        patch_count=len(patches), changed_files=sorted(files))

        require(directory_snapshot(source, mirrorable_only=True)["files"] == baseline["files"],
                "Source changed during integration; no files were written")
        backup = Path(temp_name) / "backup"
        backed_up, newly_created = [], []
        try:
            for name in sorted(files):
                source_path, candidate_path = source / name, candidate / name
                if source_path.exists():
                    backup_path = backup / name
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, backup_path)
                    backed_up.append(name)
                else:
                    newly_created.append(name)
                if candidate_path.is_file():
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate_path, source_path)
                else:
                    source_path.unlink(missing_ok=True)
        except Exception:
            for name in newly_created:
                (source / name).unlink(missing_ok=True)
            for name in backed_up:
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup / name, target)
            raise
    return dict(status="applied", source_mode="temporary-git-mirror",
                patch_count=len(patches), changed_files=sorted(files))


def integrate(workdir, patches, apply=False):
    workdir = resolved(workdir)
    require(workdir.is_dir(), "Work directory does not exist")
    return integrate_git(root(workdir), patches, apply) if is_git_root(workdir) else integrate_plain(workdir, patches, apply)


def main():
    p = argparse.ArgumentParser(description="Check or explicitly apply Codex-reviewed router patches")
    p.add_argument("--workdir", required=True)
    p.add_argument("--patch", action="append", required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    a = p.parse_args()
    workdir = resolved(a.workdir)
    if is_git_root(workdir):
        with lock(root(workdir)):
            result = integrate_git(workdir, a.patch, a.apply)
    else:
        result = integrate_plain(workdir, a.patch, a.apply)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
