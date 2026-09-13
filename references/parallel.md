# Isolated worktree dispatch

1. Start from a clean committed root. Read repo instructions and review verifier commands first.
2. Provide a new run directory outside the repo, a plan, and 1–3 workers.
3. The dispatcher compiles the plan and selects eligible non-overlapping candidates. Inspect `not_dispatched`; skipped work has not been completed.
4. It serially creates detached worktrees at the same HEAD, then routes each selected task independently. The repository CLI lock excludes other router commands sharing its Git common directory; it does not lock editors or unrelated programs.
5. Passing runs export `tasks/<id>/result.patch` plus `route-result.json`. A successful worktree is removed only after export. Failed worktrees are retained and listed in `dispatch-result.json`; inspect them before any cleanup.
6. Review all patches and integrate explicitly. Passing individual tasks does not prove combined compatibility; run combined tests.

Worktrees do not include untracked/ignored files, local virtual environments, or uncommitted changes from the primary checkout. Direct `route.py` rejects any pre-existing ignored files before starting a worker, preserving local notes and other data that Git status would otherwise hide. Dependencies must already be accessible outside the worker checkout; missing dependencies cause a stop. Do not copy `.env`, credentials, or unrelated local data to make a worktree run. No automatic package installation or dirty-worktree stash/reset is performed. Verifiers must not leave new cache/build files in the checkout, even when ignored.

Git worktrees share Git metadata and are not security boundaries. The full-access SDK shell can access anything the operating system permits, including shared Git files, the primary checkout and ignored files. Worker checks examine HEAD, index, all tracked/untracked/ignored files, scope, file counts, and output size. The separate primary-checkout comparison also hashes tracked, untracked, and ignored files. It still cannot comprehensively monitor shared Git metadata or activity outside the repository. Use a restricted VM/container when real isolation is needed, or keep the task in Codex.

If an interrupted process leaves a lock or worktree, inspect the recorded PID, Git worktree inventory, and run outputs. Remove only confirmed stale resources created by that run; never reset or clean user files as a recovery shortcut.
