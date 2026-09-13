---
name: smart-deepseek-router
description: Use a DeepSeek-first workflow for bounded, testable repository implementation while Codex retains contracts, architecture decisions, host verification, and review. Supports scoped coding, refactoring, tests, context-heavy repository work, repetitive migrations, isolated Git worktrees, limited Flash-to-Pro escalation, and reviewed patch integration. Keep secrets, deployments, destructive actions, and external mutations in Codex.
---

# Smart DeepSeek Router v0.8.0

Use a DeepSeek-first split: Codex defines scope and acceptance, DeepSeek performs bounded repository implementation and inspection, and Codex reviews host-verified patches. The transparent routing heuristic favors context-heavy implementation when the task remains bounded and verifiable. See [upstream sources and compatibility](references/sources.md).

## Before routing

- Read applicable repository instructions, inspect Git status, and resolve architecture, product behavior, security, and data-integrity decisions in Codex. Once scope and acceptance are concrete, prefer DeepSeek for the implementation, including small, repetitive, or context-heavy repository work. Keep the work in Codex when delegation overhead exceeds the likely implementation effort or the result cannot be independently verified.
- Use this workflow only for authorized repository tasks with concrete, executable acceptance checks. Keep secrets, deployments, destructive actions, external mutations, and policy decisions out of delegated contracts.
- Run `python <skill-dir>/scripts/run.py doctor --online` before the first live route or after provider changes. Planning, patch checks, and offline tests need only Python 3.10+ and Git. Live execution also needs the compatible official SDK/runtime, a working platform shell, a configured DeepSeek key, and a recent model capability cache. If the dedicated runtime is missing, read [runtime setup](references/runtime.md) and run the explicit installer only with the user's authorization. On Windows, `configure.py` can store the key for the current user with DPAPI; other platforms use their secure environment configuration. Never ask for a key in chat or call a paid model only to test installation.
- Workers use the official `sdk-minimal` profile with a fresh Harness home per attempt. **This profile has full local process access. A Git worktree is not a security sandbox.** Only use trusted, non-sensitive repositories in an appropriately isolated execution environment. Scope checks are post-run checks, not access control. The worker receives a per-attempt loopback token; a host proxy holds the real provider key, forces the assigned model, and caps requests and output tokens. This protects the provider credential from ordinary worker environment inspection, but does not restrict access to other OS-visible files. If the environment is unsuitable, continue directly in Codex.
- All routing requires a clean repository root with an existing commit. Direct worker checkouts must also contain no pre-existing ignored files; isolated dispatch creates fresh worktrees without the primary checkout's ignored local data. Preserve dirty user work; keep the task in Codex or prepare an authorized separate clean checkout without discarding changes. This deliberately tightens the supplied v0.3 sequential fallback. Symlink/submodule repositories require a different reviewed workflow.

## Plan candidates

Describe independently bounded slices using [the plan schema](references/plan.md) and [routing rules](references/routing.md). Set objective, exact file/directory write scope, acceptance, trusted verifier commands, and boolean traits. Let the script compute the score; do not invent a score in conversation.

```text
python <skill-dir>/scripts/run.py plan --plan <candidate-plan.json> --out-dir <new-planning-dir>
```

Read `routing.json`, including tasks kept in Codex and scope conflicts. Contracts are written to `contracts/<id>.json`. The included [example plan](references/example-plan.json) is a schema example; adapt its paths and tests before executing.

Let DeepSeek read the repository context needed to implement the contract. Codex should avoid duplicating that investigation before dispatch unless it is needed to define architecture, scope, or acceptance. Afterward, review the actual diff and host evidence rather than recreating the worker's full reasoning.

## Execute

Read [parallel rules](references/parallel.md) for multiple independent, non-overlapping, dependency-stable candidates:

```text
python <skill-dir>/scripts/run.py dispatch --workdir <clean-repo-root> --plan <candidate-plan.json> --run-dir <new-outside-repo-dir> --max-workers 3
```

Dispatch uses detached worktrees, exports passing binary patches, and leaves the primary checkout unchanged under normal execution. Failed worktrees remain for inspection. Scope checks cannot prevent a misbehaving process from accessing the primary checkout; the final primary-state comparison includes tracked, untracked, and ignored files.

For one task, prefer dispatch with `--max-workers 1` if it is independent. For explicit direct editing of a clean authorized worktree:

```text
python <skill-dir>/scripts/run.py route --workdir <clean-authorized-worktree> --contract <contract.json> --run-dir <new-outside-repo-dir> --result-out <new-outside-repo-result.json>
```

`route.py` directly changes that worktree and preserves failed attempts for review. It does not silently roll them back. Every run directory must be new and outside the target repository. Do not run multiple router instances against the same repository; CLI entry points take a repository lock.

Contracts default to `model_policy: "auto"`: Codex scores task difficulty from the six routing traits, sends straightforward bounded work (score below 9) to Flash, and sends harder or context-heavy work (score 9 or higher) directly to `deepseek-v4-pro`. Set `model_policy: "flash-first"` or `"pro-only"` to override that decision explicitly. Auto/Flash routes may use one evidence-backed Pro retry only when `allow_pro: true`; explicit Pro-only never retries. Empty changes fail by default. Read [escalation rules](references/escalation.md). Worker text is never completion evidence. Missing SDKs, credentials, incomplete turns, timeouts, permission errors, and dependency failures do not trigger escalation.

## Review and integrate

Read the route result, changed code, and patch, checking correctness against the contract. A passing verifier is evidence, not automatic authorization for unrelated work. See [integration](references/integration.md).

```text
python <skill-dir>/scripts/run.py integrate --workdir <primary-repo> --patch <reviewed-task/result.patch> --check
python <skill-dir>/scripts/run.py integrate --workdir <primary-repo> --patch <reviewed-task/result.patch> --apply
```

Supply multiple reviewed patches with repeated `--patch`. Both commands require a clean checkout at the recorded base commit and matching patch hashes. `--apply` is an explicit Codex action within the user's existing authorization, not an unconditional new confirmation request. No automatic merge or commit is performed. Run combined tests and inspect the final diff after integration; Codex owns remaining correctness and conflict resolution.

Report which tasks ran, model attempts, host verification, resulting files, and unresolved limits. Distinguish local/offline tests from an actual live DeepSeek run.
