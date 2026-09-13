# Smart DeepSeek Router — Bilingual Usage Guide / 双语使用指南

This document is the complete bilingual reference for installing and using the `smart-deepseek-router` Codex skill. It is aligned with the quick start in `README.md`.

本文档是安装和使用 `smart-deepseek-router` Codex 技能的完整双语参考，与 `README.md` 中的快速入门保持一致。

## What this skill does / 技能用途

`smart-deepseek-router` is a DeepSeek-first skill for bounded, testable repository implementation. Codex defines the contract, write scope, and acceptance checks; DeepSeek performs scoped implementation and repository investigation; Codex reviews the resulting diff and host-verified evidence. The router provides strict normalized contracts, isolated Git worktrees, dynamic Flash/Pro capability discovery, a loopback credential proxy, request/output limits, host-run acceptance verifiers, and reviewed binary patch export.

`smart-deepseek-router` 是一个以 DeepSeek 为先的技能，用于有界、可测试的仓库实现任务。Codex 定义合同、写入范围和验收检查；DeepSeek 执行有范围的实现和仓库调查；Codex 审查最终差异和宿主验证的证据。路由器提供严格的规范化合同、隔离的 Git worktree、动态 Flash/Pro 能力发现、回环凭据代理、请求/输出限制、宿主导出的验收检查，以及经审查的二进制补丁导出。

## Requirements / 前置条件

- Codex with local skill support / 支持本地技能的 Codex
- Python 3.10 or newer / Python 3.10 或更高版本
- Git
- PowerShell on Windows, or Bash on Linux/macOS / Windows 上的 PowerShell，或 Linux/macOS 上的 Bash
- A DeepSeek API key / 一个 DeepSeek API 密钥
- Network only for `install_runtime.py` and live DeepSeek runs / 仅 `install_runtime.py` 和在线 DeepSeek 运行需要网络

## Install / 安装

The skill must live under Codex's skills directory. When `CODEX_HOME` is set, clone into `$CODEX_HOME/skills/smart-deepseek-router`. When it is unset, use the Codex default `~/.codex/skills/smart-deepseek-router`.

技能必须位于 Codex 的技能目录下。设置 `CODEX_HOME` 时，请克隆到 `$CODEX_HOME/skills/smart-deepseek-router`。未设置时，请使用 Codex 默认目录 `~/.codex/skills/smart-deepseek-router`。

Linux/macOS:

```bash
SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/awei-duanduan/smart-deepseek-router.git "$SKILLS_DIR/smart-deepseek-router"
cd "$SKILLS_DIR/smart-deepseek-router"
python3 scripts/install_runtime.py
```

Windows PowerShell:

```powershell
$SkillsDir = if ($env:CODEX_HOME) { "$env:CODEX_HOME\skills" } else { "$env:USERPROFILE\.codex\skills" }
git clone https://github.com/awei-duanduan/smart-deepseek-router.git "$SkillsDir\smart-deepseek-router"
cd "$SkillsDir\smart-deepseek-router"
python scripts/install_runtime.py
```

Do not clone directly into a repository or a pre-existing non-empty directory. Use a clean skill directory.

请勿直接克隆到仓库内部或已存在的非空目录。请使用干净的技能目录。

## Explicit runtime installer / 显式运行时安装器

Run the explicit installer `scripts/install_runtime.py`. It creates a dedicated virtual environment outside the skill directory and installs the compatibility-tested pinned runtime:

请运行显式安装器 `scripts/install_runtime.py`。它会在技能目录之外创建专用虚拟环境，并安装经过兼容性测试的固定运行时：

```bash
python scripts/install_runtime.py
```

The default version is `deepseek-harness-sdk==0.1.5rc1`, which pulls a same-version `deepseek-harness-runtime-bin`. Override only after reviewing upstream changes and rerunning tests:

默认版本为 `deepseek-harness-sdk==0.1.5rc1`，它会安装同版本的 `deepseek-harness-runtime-bin`。仅在审查上游变更并重新运行测试后才能覆盖版本：

```bash
python scripts/install_runtime.py --version 0.1.5rc1
```

After installation, always run router commands through `scripts/run.py` so the dedicated Python interpreter and, on Windows, the DPAPI-encrypted key are selected.

安装后，请始终通过 `scripts/run.py` 运行路由器命令，以便选择专用 Python 解释器；在 Windows 上还会载入 DPAPI 加密的密钥。

## Configure the DeepSeek API key / 配置 DeepSeek API 密钥

Never paste a real key into chat, a plan, a contract, or a shell command line. Configure it locally and securely.

切勿将真实密钥粘贴到聊天、计划、合同或 shell 命令行中。请在本地安全地配置。

### Linux/macOS / Linux/macOS

Set `DEEPSEEK_API_KEY` in your secure environment configuration, for example a protected shell profile or a secret manager. Start a new shell afterward.

在安全的环境配置中设置 `DEEPSEEK_API_KEY`，例如受保护的 shell 配置文件或密钥管理器。然后启动新的 shell。

```bash
export DEEPSEEK_API_KEY="sk-your-deepseek-api-key"
```

The optional `DEEPSEEK_BASE_URL` selects an explicitly configured compatible endpoint and is part of the capability-cache identity:

可选的 `DEEPSEEK_BASE_URL` 用于选择明确配置的兼容端点，并作为能力缓存标识的一部分：

```bash
export DEEPSEEK_BASE_URL="https://your-compatible-endpoint.example"
```

### Windows / Windows

Prefer the local DPAPI form. It opens a short-lived loopback-only page, encrypts the key for the current Windows user, verifies it against the official model list, and never writes the key to chat or logs:

推荐使用本地 DPAPI 表单。它会打开一个短期的仅回环页面，为当前 Windows 用户加密密钥，对照官方模型列表进行验证，并且绝不会将密钥写入聊天或日志：

```powershell
python scripts/run.py configure --state "$env:TEMP\smart-deepseek-router-config.json"
```

Alternatively, set a Windows User environment variable (this stores the key in the user environment, not in DPAPI):

或者，设置 Windows 用户环境变量（这会将密钥存储在用户环境中，而非 DPAPI 中）：

```powershell
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-your-deepseek-api-key", "User")
```

Restart the terminal after setting a user environment variable so `scripts/run.py` can see it.

设置用户环境变量后请重启终端，以便 `scripts/run.py` 能够读取到它。

## Doctor / 诊断检查

Run `doctor --online` before the first live route and after provider or model changes. It refreshes the official model list, records selected Flash/Pro ids, and reports readiness. It never prints the key and never installs anything.

在首次实际路由之前以及提供商或模型变更后，请运行 `doctor --online`。它会刷新官方模型列表，记录选定的 Flash/Pro ID，并报告就绪状态。它绝不打印密钥，也绝不安装任何东西。

```bash
python scripts/run.py doctor --online
```

Without `--online`, doctor uses a capability cache valid for 24 hours:

不带 `--online` 时，doctor 使用有效期为 24 小时的能力缓存：

```bash
python scripts/run.py doctor
```

Check `ready_for_live_attempt` first. A positive report checks runtime compatibility, key presence, shell availability, and a recent capability cache; it does not prove billing capacity or OS isolation.

请首先查看 `ready_for_live_attempt`。正常报告表示运行时兼容、密钥存在、shell 可用且能力缓存较新；它不能证明计费额度或操作系统隔离。

## Use in Codex / 在 Codex 中使用

Invoke the skill explicitly with `$smart-deepseek-router`:

请通过 `$smart-deepseek-router` 显式调用该技能：

```text
Use $smart-deepseek-router to implement this bounded change and verify it with the repository tests: ...
```

### Flash-first default / 默认 Flash 优先

Contracts default to `model_policy: "flash-first"`. The router runs optional preflight checks, discovers currently available model ids, and tries the advertised Flash model. Acceptance checks run only after the worker, so they may assert behavior that does not exist on the baseline. A normally completed, in-scope Flash attempt with classified acceptance failures can use one Pro retry only when `allow_pro: true` and a verifier has a specific `implementation_failure_pattern`. Missing SDKs, credentials, incomplete turns, timeouts, permission errors, and dependency failures do not trigger escalation.

合同默认使用 `model_policy: "flash-first"`。路由器运行可选的预检，发现当前可用的模型 ID，并尝试宣传的 Flash 模型。验收检查仅在 worker 之后运行，因此它们可以断言基线中不存在的行为。只有正常完成、范围内的 Flash 尝试在验收失败且 `allow_pro: true`、检查器具有明确的 `implementation_failure_pattern` 时，才能使用一次 Pro 重试。缺少 SDK、凭据、未完成回合、超时、权限错误和依赖故障都不会触发升级。

### Pro-only direct use / 直接使用 Pro-only

When the user explicitly asks for DeepSeek Pro, Pro-only, or to skip Flash, set `model_policy: "pro-only"` without asking again. The router then invokes `deepseek-v4-pro` directly and only, with no Flash attempt and no escalation retry. In a contract or plan, use:

当用户明确要求使用 DeepSeek Pro、Pro-only 或跳过 Flash 时，请直接设置 `model_policy: "pro-only"`，不要再次询问。路由器随后将直接且仅调用 `deepseek-v4-pro`，不尝试 Flash，也不进行升级重试。在合同或计划中，请使用：

```json
"model_policy": "pro-only"
```

Example Codex instruction:

Codex 调用示例：

```text
Use $smart-deepseek-router with DeepSeek Pro only for this bounded repository task: ...
```

## Plan / 规划

Describe independently bounded slices with the plan schema. Set objective, exact file/directory write scope, acceptance, trusted verifier commands, and boolean traits. Let the script compute the routing score.

使用计划模式描述独立的有界切片。设置目标、精确的文件/目录写入范围、验收、受信任的检查命令和布尔特征。让脚本计算路由分数。

```bash
python scripts/run.py plan --plan references/example-plan.json --out-dir ../plans/router-plan
```

The command writes `routing.json` (scoring and scope-conflict results) and normalized `contracts/<id>.json`. The included `references/example-plan.json` is a schema example; adapt its paths and tests before executing.

该命令会写入 `routing.json`（评分和范围冲突结果）以及规范化合同 `contracts/<id>.json`。自带的 `references/example-plan.json` 只是模式示例；执行前请调整其路径和测试。

## Dispatch / 分派

For multiple independent, non-overlapping, dependency-stable candidates, use dispatch. It creates detached worktrees at the same HEAD, routes each selected task independently, and exports passing binary patches. Failed worktrees remain for inspection.

对于多个独立、不重叠、依赖稳定的候选任务，请使用 dispatch。它会在同一 HEAD 创建分离工作树，独立路由每个选定的任务，并导出通过的二进制补丁。失败的工作树会保留以供检查。

```bash
python scripts/run.py dispatch --workdir /path/to/clean-repo-root --plan ../plans/candidate-plan.json --run-dir ../runs/dispatch-run --max-workers 3
```

For one task, prefer dispatch with `--max-workers 1` if the task is independent. Inspect `not_dispatched`; skipped work has not been completed.

对于单个任务，如果任务独立，建议使用 `--max-workers 1`。请检查 `not_dispatched`；被跳过的工作尚未完成。

## Route / 路由

For explicit direct editing of a clean authorized worktree, use route. It directly changes that worktree and preserves failed attempts for review; it does not silently roll them back.

对于明确授权直接编辑的干净工作树，请使用 route。它会直接更改该工作树，并保留失败的尝试以供审查；它不会静默回滚。

```bash
python scripts/run.py route --workdir /path/to/clean-authorized-worktree --contract ../plans/router-plan/contracts/my-task.json --run-dir ../runs/my-task-run --result-out ../runs/my-task-run/route-result.json
```

Every run directory must be new and outside the target repository. Do not run multiple router instances against the same repository; CLI entry points take a repository lock.

每个运行目录必须是新的，并且位于目标仓库之外。不要对同一仓库运行多个路由器实例；CLI 入口会获取仓库锁。

## Integrate / 集成

Review the route result, changed code, and patch, checking correctness against the contract. A passing verifier is evidence, not automatic authorization for unrelated work. Then integrate reviewed patches:

审查路由结果、更改的代码和补丁，对照合同检查正确性。通过的检查是证据，不是对无关工作的自动授权。然后集成经审查的补丁：

```bash
python scripts/run.py integrate --workdir /path/to/primary-repo --patch ../runs/dispatch-run/tasks/my-task/result.patch --check
python scripts/run.py integrate --workdir /path/to/primary-repo --patch ../runs/dispatch-run/tasks/my-task/result.patch --apply
```

Supply multiple reviewed patches with repeated `--patch`. Both commands require a clean checkout at the recorded base commit and matching patch hashes. `--check` changes no files. `--apply` applies all nonempty patches in one Git invocation without `--reject`, leaving changes unstaged. It does not commit, push, merge, deploy, or ask for redundant approval. After integration, run combined tests and inspect the final diff.

可使用多个 `--patch` 提供多个经审查的补丁。两个命令都要求检出处于记录的 base commit 且补丁哈希匹配。`--check` 不会更改文件。`--apply` 在一次 Git 调用中应用所有非空补丁，不使用 `--reject`，并且不暂存更改。它不会提交、推送、合并、部署或要求重复批准。集成后，请运行组合测试并检查最终差异。

## Contract fields / 合同字段

The normalized contract contains every execution default. Unknown root, task, contract, and verifier fields are rejected. Use `/` in contract paths even on Windows. No absolute paths, drive paths, globs, `..`, credential filenames, or `.git` paths.

规范化合同包含每个执行默认值。未知的根、任务、合同和检查器字段都会被拒绝。即使在 Windows 上，合同路径也请使用 `/`。不允许绝对路径、盘符路径、通配符、`..`、凭据文件名或 `.git` 路径。

| Field / 字段 | Meaning / 含义 | Default / 默认值 |
|---|---|---|
| `schema_version` | Plan root schema version / 计划根模式版本 | `2` |
| `tasks[].id` | Unique lowercase letters/digits/underscore/hyphen, max 64 characters / 唯一的小写字母/数字/下划线/连字符，最长 64 字符 | required / 必填 |
| `objective` | Concrete bounded change, with no credentials / 具体有界变更，不含凭据 | required / 必填 |
| `scope` | Non-empty list of exact files or directories ending in `/`, relative to repo root / 非空的精确文件列表或以 `/` 结尾的目录列表，相对于仓库根 | required / 必填 |
| `acceptance` | Non-empty list of observable outcomes / 非空的可观察结果列表 | required / 必填 |
| `preflight_verifiers` | Host checks that must already pass before a worker runs / worker 运行前必须已通过的宿主检查 | `[]` |
| `acceptance_verifiers` | Non-empty host checks for the requested post-worker behavior / 非空的请求后行为宿主检查 | required / 必填 |
| `verifier_paths` | Trusted verifier files workers must not modify; exclude these from scope / worker 不得修改的受信检查文件；请将其排除出范围 | optional / 可选 |
| `traits` | Six routing booleans: `bounded`, `verifiable`, `independent`, `dependency_stable`, `repetitive`, `context_heavy` / 六个路由布尔值 | required / 必填 |
| `blockers` | Applicable hard blockers: `secrets`, `deployment`, `destructive`, `external_side_effects`, `policy_decision`, `unverifiable`; use `[]` when none / 适用的硬性阻断项；无则 `[]` | `[]` |
| `depends_on` | Other task ids; any dependency prevents automatic parallel scheduling / 其他任务 id；任何依赖都会阻止自动并行调度 | `[]` |
| `allow_pro` | Permit at most one evidence-backed Pro retry / 允许至多一次有证据支持的 Pro 重试 | `false` |
| `model_policy` | `flash-first` or `pro-only`; `pro-only` invokes `deepseek-v4-pro` directly and only, with no Flash attempt or escalation / `flash-first` 或 `pro-only`；`pro-only` 直接且仅调用 `deepseek-v4-pro`，不尝试 Flash，也不升级 | `flash-first` |
| `allow_noop` | Accept a verified empty patch only for an explicitly observational task / 仅对明确的观察性任务接受已验证的空补丁 | `false` |
| `task_timeout_seconds` | Per-attempt timeout (1–3600); launcher adds 40 seconds for boot/shutdown / 每次尝试超时（1–3600）；启动器另加 40 秒用于启动/关闭 | `600` |
| `max_provider_requests` | Provider request cap per attempt (1–100), enforced by the credential proxy / 每次尝试的提供商请求上限（1–100），由凭据代理强制执行 | `24` |
| `max_model_output_tokens` | Output cap per request (512–32768), enforced by SDK and proxy / 每次请求输出上限（512–32768），由 SDK 和代理强制执行 | `8192` |
| `max_changed_files` | Changed file count cap (1–10000) / 更改文件数量上限（1–10000） | `200` |
| `max_changed_bytes` | Resulting file byte cap (1–1 GiB) / 结果文件字节上限（1–1 GiB） | `20971520` (20 MiB) |
| `max_patch_bytes` | Patch byte cap (1–2 GiB) / 补丁字节上限（1–2 GiB） | `41943040` (40 MiB) |

Each verifier has an `argv` string list executed without a shell, optional `cwd` inside the repository (default `.`), and `timeout_seconds` (default 120; 1–3600). `{python}` means the same Python interpreter running the router. Commands that need shell syntax must explicitly name a shell and be reviewed as executable code. Do not put secrets in argv.

每个检查器都有不带 shell 执行的 `argv` 字符串列表、可选的仓库内 `cwd`（默认 `.`）和 `timeout_seconds`（默认 120；1–3600）。`{python}` 表示运行路由器的同一个 Python 解释器。需要 shell 语法的命令必须显式指定 shell，并作为可执行代码进行审查。不要在 argv 中放入密钥。

## Review flow / 审查流程

1. Read the route result, changed code, and patch. Check correctness against the contract, scope, and acceptance.
2. Treat host verification as evidence, not proof of all behavior, and not automatic authorization for unrelated work.
3. Run `integrate --check` before `integrate --apply`; apply only after your own review and within the user's existing authorization.
4. Run combined tests and inspect the final diff after integration. Failed runs are never auto-reverted; inspect retained worktrees for useful work.
5. Report which tasks ran, model attempts, host verification, resulting files, and unresolved limits. Distinguish local/offline tests from a live DeepSeek run.

1. 阅读路由结果、更改的代码和补丁。对照合同、范围和验收检查正确性。
2. 将宿主验证视为证据，而非所有行为的证明，也不是对无关工作的自动授权。
3. 在 `integrate --apply` 之前运行 `integrate --check`；仅在自行审查且用户已授权的情况下应用。
4. 集成后运行组合测试并检查最终差异。失败的运行绝不会自动回滚；请检查保留的工作树以恢复有用工作。
5. 报告运行了哪些任务、模型尝试、宿主验证、结果文件和未解决的限制。区分本地/离线测试与实际的 DeepSeek 运行。

## Troubleshooting / 故障排查

| Symptom / 症状 | Likely cause / 可能原因 | Fix / 处理 |
|---|---|---|
| `Dedicated runtime is missing` | `install_runtime.py` was not run, or the skill directory moved / 未运行 `install_runtime.py`，或技能目录已移动 | Run `python scripts/install_runtime.py` from the skill directory / 在技能目录中运行 `python scripts/install_runtime.py` |
| `doctor --online` reports `ready_for_live_attempt: false` | Missing Python 3.10+/Git/shell, incompatible SDK, no key, or stale Flash capability / 缺少 Python 3.10+/Git/shell、SDK 不兼容、没有密钥或 Flash 能力过期 | Read the JSON fields and fix the first false item, then rerun `python scripts/run.py doctor --online` / 阅读 JSON 字段并修复第一个 false 项，然后重新运行 `python scripts/run.py doctor --online` |
| `model_discovery_error` | Network/proxy failure or invalid `DEEPSEEK_BASE_URL` / 网络/代理故障或 `DEEPSEEK_BASE_URL` 无效 | Verify network, endpoint, and key; rerun `doctor --online` / 检查网络、端点和密钥，然后重新运行 `doctor --online` |
| Windows configure reports `DeepSeek rejected this key` | Invalid API key / API 密钥无效 | Check the key at the official DeepSeek console; it was not saved / 在 DeepSeek 官方控制台检查密钥；该密钥不会被保存 |
| `integrate` reports base or hash mismatch | Patch changed, wrong base, or overlapping scopes / 补丁已更改、base 错误或范围重叠 | Stop and resolve/rebase/reverify in Codex; never edit the recorded hash / 在 Codex 中停止并解决/变基/重新验证；切勿编辑记录的哈希 |
| Stale lock or worktree after an interrupted run / 中断后出现残留锁或工作树 | Interrupted router process / 路由器进程被中断 | Inspect the recorded PID and Git worktree inventory; remove only confirmed stale resources from that run / 检查记录的 PID 和 Git worktree 清单；只移除经确认的该运行残留资源 |

## Security limitations / 安全限制

Read [SECURITY.md](../SECURITY.md) before using the skill. The worker uses the official `sdk-minimal` profile with full local process access. A Git worktree is not a security sandbox. Scope checks are post-run checks, not access control. The host proxy holds the real provider key, forces the assigned model, and caps requests and output tokens; this protects the credential from ordinary worker environment inspection but does not restrict access to other OS-visible files. Only use trusted, non-sensitive repositories in an appropriately isolated execution environment. Keep secrets, deployments, destructive actions, external mutations, and policy decisions in Codex. Use a restricted VM or container when real isolation is required. Treat run directories as private working data.

使用前请阅读 [SECURITY.md](../SECURITY.md)。worker 使用官方 `sdk-minimal` 配置，拥有完整的本地进程访问权限。Git worktree 不是安全沙箱。范围检查是事后检查，不是访问控制。宿主代理持有真实提供商密钥，强制使用指定模型，并限制请求和输出令牌；这可以保护凭据不被普通的 worker 环境检查读取，但不会限制对操作系统可见的其他文件的访问。仅在适当隔离的执行环境中使用受信任、非敏感的仓库。将秘密、部署、破坏性操作、外部变更和策略决定保留在 Codex 中。需要真正隔离时，请使用受限的虚拟机或容器。请将运行目录视为私有工作数据。

## Offline tests / 离线测试

Offline tests do not call DeepSeek and do not require an API key. They exercise router logic only; they do not prove the packaged live runtime works.

离线测试不会调用 DeepSeek，也不需要 API 密钥。它们只测试路由器逻辑，不能证明打包的在线运行时可用。

```bash
python -B -m unittest discover -s tests -v
```

## Related documents / 相关文档

- [SKILL.md](../SKILL.md) — agent workflow / 代理工作流
- [SECURITY.md](../SECURITY.md) — security policy / 安全策略
- `references/plan.md` — contract schema / 合同模式
- `references/routing.md` — routing heuristic / 路由启发式
- `references/escalation.md` — Flash-to-Pro escalation / Flash 到 Pro 的升级
- `references/integration.md` — review and apply / 审查与应用
- `references/runtime.md` — runtime and Windows support / 运行时与 Windows 支持
- `references/parallel.md` — isolated worktree dispatch / 隔离工作树分派