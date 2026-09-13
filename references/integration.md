# Review and apply

Passing task artifacts are `result.patch` and adjacent `route-result.json`, containing base commit, SHA-256, changed filenames/bytes, model attempts, and host verification. Keep these two files together when moving a run result. Empty patches are rejected unless the contract explicitly sets `allow_noop: true` for an observational task.

Read the patch and code, verify the task's observable behavior and scope, and review baseline/final checks. The recorded checks are evidence about this attempt, not a proof of all behavior. Artifacts are local review metadata, not cryptographically signed attestations against a malicious worker.

`integrate.py --check` requires a clean root at the same base commit, checks the patch hash, rejects overlapping file sets, and asks Git to check all patches in a single invocation. It does not change files.

`integrate.py --apply` repeats these checks and applies all nonempty patches in one Git invocation without `--reject`, leaving changes unstaged. It does not commit, push, merge a branch, deploy, or ask for redundant approval. Codex should apply only after its review and within the user's existing authorization. Concurrent external edits remain possible; keep the checkout quiescent during integration.

Apply disjoint patches from the same base together. If HEAD changed, the patch changed, or scopes overlap, stop and resolve/rebase/reverify in Codex rather than disabling integrity checks. Do not edit the recorded hash to silence a mismatch. Direct `route.py` runs already modify their authorized worktree; inspect and test that state rather than applying its patch a second time there.

After integration, run relevant combined tests, inspect the final diff, and report the actual result. Failed runs are never auto-reverted; their retained worktrees let Codex recover useful work without silently discarding it.
