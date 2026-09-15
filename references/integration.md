# Review and apply

Passing task artifacts are `result.patch` and adjacent `route-result.json`, containing base commit, SHA-256, changed filenames/bytes, model attempts, and host verification. Keep these two files together when moving a run result. Empty patches are rejected unless the contract explicitly sets `allow_noop: true` for an observational task.

Read the patch and code, verify the task's observable behavior and scope, and review baseline/final checks. The recorded checks are evidence about this attempt, not a proof of all behavior. Artifacts are local review metadata, not cryptographically signed attestations against a malicious worker.

For a Git source, `integrate.py --check` requires a clean root at the same base commit. For an ordinary source directory, it requires the adjacent `source-manifest.json`, verifies that the source still matches the recorded hashes, builds a fresh temporary Git candidate, and asks Git to check all patches there. Both modes check patch hashes and reject overlapping file sets without changing source files.

`integrate.py --apply` repeats these checks. Git sources receive all patches in one Git invocation without `--reject`, leaving changes unstaged. Ordinary directories are checked in a fresh mirror, checked again for concurrent edits, and then only the validated changed files are copied/deleted with rollback backups for write errors. It does not commit, push, merge a branch, or deploy.

Apply disjoint patches from the same base together. If HEAD changed, the patch changed, or scopes overlap, stop and resolve/rebase/reverify in Codex rather than disabling integrity checks. Do not edit the recorded hash to silence a mismatch. Direct `route.py` runs already modify their authorized worktree; inspect and test that state rather than applying its patch a second time there.

After integration, run relevant combined tests, inspect the final diff, and report the actual result. Failed runs are never auto-reverted; their retained worktrees let Codex recover useful work without silently discarding it.
