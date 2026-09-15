---
name: smart-deepseek-router
description: Use when a repository task is bounded, testable, and may benefit from routing implementation work across Astra, Sol, Terra, Luna, DeepSeek Pro, or DeepSeek Flash while preserving Codex control over architecture, safety, verification, and integration.
---

# Smart DeepSeek Router v0.11.0

Use an Astra-led split: Astra defines scope and acceptance, selects the least expensive capable executor, and summarizes evidence; the selected worker performs bounded repository implementation or inspection; Astra reviews host-verified results and controls integration. The transparent routing heuristic favors low-cost execution when the task remains bounded and verifiable. See [upstream sources and compatibility](references/sources.md).

## Astra coordination and model routing

Treat Astra as the task coordinator and final synthesizer. Astra should emit short contracts, avoid repeating repository investigation, and spend tokens only on scope, risk, routing, review, and summary. Use the lowest capable executor and escalate only when task difficulty, uncertainty, or failed verification justifies it.

Use this capability ladder:

| Task profile | Preferred executor | Astra responsibility |
|---|---|---|
| Repetitive edits, simple inspection, routine tests | DeepSeek Flash | Contract and brief review |
| Context-heavy but bounded implementation | DeepSeek Pro | Contract and evidence review |
| Simple Codex reasoning or small repair | Luna | Contract and brief review |
| Medium implementation, debugging, or test design | Terra | Contract and evidence review |
| Complex cross-module work or substantial uncertainty | Sol | Architecture, contract, and review |
| Ambiguous architecture, security, irreversible decisions, or recovery | Astra | Direct handling and final decision |

This is a direct-assignment policy, not a retry chain. Classify every independent task before execution, assign it directly to the lowest model tier that meets its difficulty, and run eligible tasks in parallel. Do not send a task to Flash first and then to Pro as the normal path. DeepSeek Flash/Pro are the direct worker models implemented by this router; Sol, Terra, and Luna are Codex-side reasoning or review tiers.

Keep secrets, deployments, destructive actions, policy decisions, and external side effects in Astra regardless of model tier. Do not use a high-capability model for repetitive edits or provider setup.

## Before routing

- Read applicable repository instructions, inspect Git status, and resolve architecture, product behavior, security, and data-integrity decisions in Astra. Once scope and acceptance are concrete, prefer the lowest capable executor, including DeepSeek Flash for small or repetitive work. Keep the work in Astra when delegation overhead exceeds the likely implementation effort or the result cannot be independently verified.
- Use this workflow only for authorized repository tasks with concrete, executable acceptance checks. Keep secrets, deployments, destructive actions, external mutations, and policy decisions out of delegated contracts.
- Run `python <skill-dir>/scripts/run.py doctor --online` before the first live route or after provider changes. Planning, patch checks, and offline tests need only Python 3.10+ and Git. Live execution also needs the local Claude Code CLI, a working platform shell, a configured DeepSeek key, and a recent model capability cache. On Windows, `configure.py` can store the key for the current user with DPAPI; other platforms use their secure environment configuration. Never ask for a key in chat or call a paid model only to test installation.
- DeepSeek workers use the local Claude Code CLI through the Anthropic-compatible endpoint. **The CLI has full local process access. A Git worktree is not a security sandbox.** Only use trusted, non-sensitive repositories in an appropriately isolated execution environment. Scope checks are post-run checks, not access control. The worker receives a per-attempt loopback token; a host proxy holds the real provider key, forces the assigned model, and caps requests and output tokens. This protects the provider credential from ordinary worker environment inspection, but does not restrict access to other OS-visible files. If the environment is unsuitable, continue directly in Codex.
- `orchestrate` accepts either a clean Git root with an existing commit or an ordinary source directory. For an ordinary directory it creates a filtered temporary Git mirror inside the new run directory, records `source-manifest.json`, and creates worker worktrees from that mirror. It excludes sensitive paths and common generated/dependency directories; unsafe symlinks are rejected. The original directory remains unchanged until Astra explicitly runs `integrate --apply`. Low-level `route` and `dispatch` still require clean committed Git roots. Preserve dirty user work; never stash, reset, or discard it automatically. Submodule repositories require a different reviewed workflow.

## Plan candidates

Describe independently bounded slices using [the plan schema](references/plan.md) and [routing rules](references/routing.md). Set objective, exact file/directory write scope, acceptance, trusted verifier commands, and boolean traits. Let the script compute the score; do not invent a score in conversation.

```text
python <skill-dir>/scripts/run.py plan --plan <candidate-plan.json> --out-dir <new-planning-dir>
```

Read `routing.json`, including tasks kept in Codex and scope conflicts. Contracts are written to `contracts/<id>.json`. The included [example plan](references/example-plan.json) is a schema example; adapt its paths and tests before executing.

Let the selected worker read the repository context needed to implement the contract. Astra should avoid duplicating that investigation before dispatch unless it is needed to define architecture, scope, or acceptance. Afterward, review the actual diff and host evidence rather than recreating the worker's full reasoning.

## Execute

For one parent task with several Astra-assigned model workers, provide a JSON plan with a `tasks` array. Each task must contain a unique `id`, a `model` (`flash`, `pro`, `luna`, `terra`, or `sol`), and a `prompt`; DeepSeek tasks also require their reviewed contract path. Codex tasks may include no-shell `verifiers` entries with `argv` and optional `timeout_seconds`. The orchestrator creates isolated worktrees, starts eligible workers concurrently, runs Codex verifiers, exports successful Codex diffs, and writes `orchestration-result.json` with per-task status and private run directories:

```text
python <skill-dir>/scripts/run.py orchestrate --repo <clean-repo-root-or-ordinary-directory> --plan <orchestration-plan.json> --run-dir <new-outside-source-dir> --max-workers 3
```

Codex workers run with the requested Codex model in an isolated managed worktree. DeepSeek workers use the Anthropic-compatible Claude Code worker and require independently isolated worktrees in their task setup. The parent receives results only; patches are never integrated automatically. Astra must review each result and apply or reject patches explicitly.

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

Contracts default to `model_policy: "auto"`; users normally omit this field. Astra scores each task from the six routing traits before execution: straightforward bounded work goes directly to Flash, while harder or context-heavy work goes directly to `deepseek-v4-pro`. Eligible independent tasks are dispatched in parallel. Luna, Terra, and Sol selection happens only when a task requires their Codex reasoning tier; it is not an automatic Flash-to-Pro or Flash-to-Codex cascade. The legacy `flash-first` and `pro-only` values remain only for compatibility with existing contracts. Empty changes fail by default. Read [escalation rules](references/escalation.md). Worker text is never completion evidence. Missing SDKs, credentials, incomplete turns, timeouts, permission errors, and dependency failures do not trigger escalation.

## Review and integrate

Read the route result, changed code, and patch, checking correctness against the contract. A passing verifier is evidence, not automatic authorization for unrelated work. See [integration](references/integration.md).

```text
python <skill-dir>/scripts/run.py integrate --workdir <primary-repo-or-source-directory> --patch <reviewed-task/result.patch> --check
python <skill-dir>/scripts/run.py integrate --workdir <primary-repo-or-source-directory> --patch <reviewed-task/result.patch> --apply
```

Supply multiple reviewed patches with repeated `--patch`. Git sources require a clean checkout at the recorded base commit. Ordinary directories require the exact recorded source snapshot; integration rebuilds a fresh candidate mirror, checks all patches there, rechecks the source for concurrent edits, and writes only validated changed files. Both modes verify patch hashes and reject overlapping file sets. `--apply` is an explicit Codex action within the user's existing authorization. No automatic merge or commit is performed. Run combined tests and inspect the final files after integration; Codex owns remaining correctness and conflict resolution.

Report which tasks ran, selected model tier, model attempts, host verification, resulting files, and unresolved limits. Keep the summary concise. Distinguish local/offline tests from an actual live DeepSeek run.
