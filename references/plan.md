# Candidate plan and normalized contract

Plan root: `{"schema_version": 2, "tasks": [...]}` with at most 32 tasks. Unknown root, task, contract, and verifier fields are rejected so misspellings cannot silently disable controls. Each task has:

| Field | Meaning |
|---|---|
| `id` | Unique lowercase letters/digits/underscore/hyphen, at most 64 characters |
| `objective` | A concrete bounded change, with no credentials |
| `scope` | Non-empty list of exact files or directories ending in `/`, relative to repo root |
| `acceptance` | Non-empty list of observable outcomes |
| `preflight_verifiers` | Optional host checks that must already pass before a worker runs |
| `acceptance_verifiers` | Non-empty host checks for the requested post-worker behavior |
| `verifier_paths` | Optional exact trusted verifier files that workers must not modify; exclude these from scope |
| `traits` | All six boolean fields from routing.md |
| `blockers` | List of applicable blocker names from routing.md; `[]` when none |
| `depends_on` | Optional other task ids; any dependency prevents automatic parallel scheduling |
| `allow_pro` | Boolean, default false; permit at most one evidence-backed Pro attempt |
| `allow_noop` | Boolean, default false; accept a verified empty patch only for an explicitly observational task |
| `task_timeout_seconds` | Integer 1–3600, default 600, per attempt; launcher adds 40 seconds for boot/shutdown |
| `max_provider_requests` | Integer 1–100, default 24, enforced by the credential proxy per attempt |
| `max_model_output_tokens` | Integer 512–32768, default 8192, enforced by SDK and proxy |
| `max_changed_files` | Integer 1–10000, default 200 |
| `max_changed_bytes` | Integer 1–1 GiB, default 20 MiB, measured from resulting files |
| `max_patch_bytes` | Integer 1–2 GiB, default 40 MiB |

Use `/` in contract paths even on Windows. No absolute paths, drive paths, globs, `..`, credential filenames, or `.git` paths. Matching is conservatively case-insensitive for cross-platform conflicts. Paths are write boundaries, not a filesystem jail; worker read access is determined by the process environment.

Each verifier has an `argv` string list (executed without a shell), optional `cwd` inside the repository (default `.`), and `timeout_seconds` (default 120; 1–3600). `{python}` means the same Python interpreter running the router. Commands that depend on shell syntax must explicitly name a shell and must be reviewed as executable code. Do not put secrets in argv. Commands and their dependencies must already be available; no auto-install.

`implementation_failure_pattern` is an optional host-authored regular expression over failure output, e.g. `AssertionError` for a known Python acceptance script. Only give a specific, justified pattern. A blanket `.*` defeats reliable failure classification. A nonzero exit alone never permits escalation. Common dependency/permission/infrastructure errors veto escalation even when a pattern matches. See escalation.md for the limitations of output classification.

Preflight checks must pass on the baseline and leave tracked, untracked, and ignored files unchanged. Acceptance checks run only after implementation, so they can require new behavior that correctly fails on the baseline. Do not duplicate acceptance checks into preflight unless the baseline is expected to pass them. Set `verifier_paths` for repository scripts used to judge correctness; do not rely solely on tests workers can rewrite. Disable test/cache writes or direct temporary build output outside the repository; Python bytecode writes are disabled in child environments. New ignored files are included in worker audits and cannot silently evade the scope check.

The normalized contract contains every execution default. Plan-only traits and dependencies remain in `routing.json`. Dependency ids must exist and cycles are rejected. Do not manually execute a contract whose dependencies remain unresolved. See [example-plan.json](example-plan.json).
