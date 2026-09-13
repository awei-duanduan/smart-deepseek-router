# Smart DeepSeek Router / 智能 DeepSeek 路由器

A DeepSeek-first Codex skill for bounded repository implementation. DeepSeek handles scoped coding and repository investigation while Codex keeps task contracts, architecture decisions, host verification, patch review, and integration control.

一个以 DeepSeek 为先的 Codex 技能，用于有边界的仓库实现任务。DeepSeek 负责受范围的编码和仓库调查，Codex 保留任务合同、架构决策、宿主验证、补丁审查和集成控制。

The router provides strict task contracts, isolated Git worktrees for parallel tasks, dynamic Flash/Pro capability discovery, a loopback credential proxy, request and output limits, host-run acceptance checks, and reviewed binary patch export.

该路由器提供严格的任务合同、用于并行任务的隔离 Git worktree、动态 Flash/Pro 能力发现、回环凭据代理、请求与输出限制、宿主导出的验收检查，以及经审查的二进制补丁导出。

## What this skill does / 技能用途

- Plans bounded, verifiable repository slices and emits normalized contracts under `contracts/<id>.json`.
- Routes one task directly into an authorized clean worktree, or dispatches multiple independent tasks into detached Git worktrees.
- Runs optional preflight checks, invokes DeepSeek through a local credential proxy, and runs host acceptance verifiers after the worker.
- Defaults to automatic model selection. Users can omit `model_policy`; Codex sends easy work to Flash and harder/context-heavy work (routing score ≥ 9) directly to `deepseek-v4-pro`. Older `flash-first` and `pro-only` values remain supported for compatibility.
- Exports reviewed binary patches with route metadata, then `integrate` applies them only after explicit Codex review.

- 将有界、可验证的仓库切片规划为规范化合同，写入 `contracts/<id>.json`。
- 将一个任务直接路由到已授权的干净 worktree，或将多个独立任务分派到分离的 Git worktree。
- 运行可选的预检，通过本地凭据代理调用 DeepSeek，并在 worker 运行后执行宿主验收检查。
- 默认自动选择模型，用户可以省略 `model_policy`：Codex 将简单任务交给 Flash，将较难或上下文较重的任务（路由分数 ≥ 9）直接交给 `deepseek-v4-pro`。旧的 `flash-first` 和 `pro-only` 值仍为兼容性保留。
- 导出经审查的二进制补丁及路由元数据，然后在 Codex 明确审查后由 `integrate` 应用。

## Requirements / 前置条件

- Codex with local skill support / 支持本地技能的 Codex
- Python 3.10 or newer / Python 3.10 或更高版本
- Git
- PowerShell on Windows, or Bash on Linux/macOS / Windows 上的 PowerShell，或 Linux/macOS 上的 Bash
- A DeepSeek API key / 一个 DeepSeek API 密钥
- Network access only for `install_runtime.py` and live DeepSeek runs / 仅 `install_runtime.py` 和在线 DeepSeek 运行需要网络

DeepSeek Harness currently runs agents with the permissions of the local process. Read [SECURITY.md](SECURITY.md) before using the skill. The security limitations in this README also apply.

DeepSeek Harness 当前以本地进程的权限运行代理。使用前请阅读 [SECURITY.md](SECURITY.md)。本 README 中的安全限制同样适用。

## Install / 安装

If `CODEX_HOME` is set, clone into `$CODEX_HOME/skills/smart-deepseek-router`. If it is unset, use Codex's default `~/.codex/skills/smart-deepseek-router`.

如果设置了 `CODEX_HOME`，请克隆到 `$CODEX_HOME/skills/smart-deepseek-router`。如果未设置，请使用 Codex 默认的 `~/.codex/skills/smart-deepseek-router`。

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

Use the explicit runtime installer `install_runtime.py` rather than a global Python environment. It creates a dedicated virtual environment outside the skill directory and installs the compatibility-tested `deepseek-harness-sdk==0.1.5rc1` runtime.

请使用显式运行时安装器 `install_runtime.py`，而不要使用全局 Python 环境。它会在技能目录之外创建专用虚拟环境，并安装经过兼容性测试的 `deepseek-harness-sdk==0.1.5rc1` 运行时。

After installation, always use `scripts/run.py` for router commands so the dedicated runtime and the configured credential are selected:

安装后，请始终使用 `scripts/run.py` 执行路由器命令，以便选择专用运行时和已配置的凭据：

```bash
python scripts/run.py doctor --online
```

On Windows, `run.py` can load a DPAPI-encrypted key into the process. On Linux/macOS, it reads `DEEPSEEK_API_KEY` from the environment.

在 Windows 上，`run.py` 可以将 DPAPI 加密的密钥载入进程。在 Linux/macOS 上，它从环境变量中读取 `DEEPSEEK_API_KEY`。

## Configure the DeepSeek API key / 配置 DeepSeek API 密钥

Never paste a real key into chat, into a plan, or onto a command line that writes command history. Use a secure local environment configuration.

切勿将真实密钥粘贴到聊天、计划或会写入命令历史的命令行中。请使用安全的本地环境配置。

Linux/macOS:

```bash
# Add this to your secure shell profile or secret manager, then start a new shell.
export DEEPSEEK_API_KEY="sk-your-deepseek-api-key"
```

Windows, either set a User environment variable:

```powershell
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-your-deepseek-api-key", "User")
```

or, preferably, use the local DPAPI form. It opens a short-lived loopback-only page, encrypts the key for the current Windows user, and never prints it:

```powershell
python scripts/run.py configure --state "$env:TEMP\smart-deepseek-router-config.json"
```

The optional `DEEPSEEK_BASE_URL` selects an explicitly configured compatible endpoint and is part of the model-capability cache identity.

可选的 `DEEPSEEK_BASE_URL` 用于选择明确配置的兼容端点，并作为模型能力缓存标识的一部分。

## Doctor / 检查

Run `doctor --online` before the first live route and after provider or model changes. It refreshes the official model list, records the selected Flash/Pro ids, and reports readiness. It never prints the key.

在首次实际路由之前以及提供商或模型变更后，请运行 `doctor --online`。它会刷新官方模型列表，记录选定的 Flash/Pro ID，并报告就绪状态。它绝不会打印密钥。

```bash
python scripts/run.py doctor --online
```

`doctor` without `--online` uses a cached capability file valid for 24 hours. A positive report is not a billing or OS-isolation guarantee.

不带 `--online` 的 `doctor` 使用有效期为 24 小时的缓存能力文件。报告正常并不保证计费或操作系统隔离。

## Use in Codex / 在 Codex 中使用

Invoke the skill explicitly with `$smart-deepseek-router`:

请通过 `$smart-deepseek-router` 显式调用该技能：

```text
Use $smart-deepseek-router to implement this bounded change and verify it with the repository tests: ...
```

Default behavior is `model_policy: "flash-first"`: the router discovers available models, tries the advertised Flash model first, and allows at most one evidence-backed Pro retry only when the contract sets `allow_pro: true` and the acceptance verifier exposes a specific `implementation_failure_pattern`.

默认行为是 `model_policy: "flash-first"`：路由器发现可用模型，先尝试宣传的 Flash 模型；仅当合同设置 `allow_pro: true` 且验收检查暴露明确的 `implementation_failure_pattern` 时，才允许至多一次有证据支持的 Pro 重试。

For a direct DeepSeek Pro-only task, set the contract policy to `pro-only` so the router invokes `deepseek-v4-pro` first and only, with no Flash attempt and no escalation retry:

对于直接的 DeepSeek Pro-only 任务，请将合同策略设为 `pro-only`，路由器将直接且仅调用 `deepseek-v4-pro`，不尝试 Flash，也不进行升级重试：

```text
Use $smart-deepseek-router with DeepSeek Pro only for this bounded repository task: ...
```

```json
"model_policy": "pro-only"
```

The skill also supports automatic selection when Codex recognizes a suitable bounded and testable repository task.

当 Codex 识别到合适的有界且可测试的仓库任务时，该技能也支持自动选择。

## Plan, route, dispatch, integrate / 规划、路由、分派、集成

All commands below are copyable templates. Replace placeholder paths with real paths outside the target repository for run/output directories. Use `/` in contract paths even on Windows.

以下命令都是可复制的模板。请将占位路径替换为真实路径；运行/输出目录必须位于目标仓库之外。即使在 Windows 上，合同路径也请使用 `/`。

Plan candidates and emit normalized contracts:

规划候选任务并生成规范化合同：

```bash
python scripts/run.py plan --plan references/example-plan.json --out-dir ../plans/router-plan
```

Read the generated `routing.json` and `contracts/<id>.json`. The example plan is a schema example; adapt its paths and tests before executing.

请阅读生成的 `routing.json` 和 `contracts/<id>.json`。示例计划只是模式示例；执行前请调整其路径和测试。

Route one task directly into a clean authorized worktree:

将一个任务直接路由到干净且已授权的工作树：

```bash
python scripts/run.py route --workdir /path/to/clean-authorized-worktree --contract ../plans/router-plan/contracts/my-task.json --run-dir ../runs/my-task-run --result-out ../runs/my-task-run/route-result.json
```

Dispatch multiple independent, non-overlapping candidates into detached worktrees:

将多个相互独立、不重叠的候选任务分派到分离工作树：

```bash
python scripts/run.py dispatch --workdir /path/to/clean-repo-root --plan ../plans/candidate-plan.json --run-dir ../runs/dispatch-run --max-workers 3
```

Review the exported patch and metadata, then integrate only after Codex review:

审查导出的补丁和元数据，并在 Codex 审查后再集成：

```bash
python scripts/run.py integrate --workdir /path/to/primary-repo --patch ../runs/dispatch-run/tasks/my-task/result.patch --check
python scripts/run.py integrate --workdir /path/to/primary-repo --patch ../runs/dispatch-run/tasks/my-task/result.patch --apply
```

`integrate --check` validates base commit, patch hash, and scope without changing files. `integrate --apply` applies reviewed patches without committing. Run combined tests and inspect the final diff after integration.

`integrate --check` 在不更改文件的情况下校验 base commit、补丁哈希和范围。`integrate --apply` 应用经审查的补丁，但不会提交。集成后请运行组合测试并检查最终差异。

## Contract fields / 合同字段

The normalized contract contains every execution default. Unknown fields are rejected. Key fields:

规范化合同包含每个执行默认值。未知字段会被拒绝。关键字段：

| Field / 字段 | Meaning / 含义 | Default / 默认值 |
|---|---|---|
| `objective` | Concrete bounded change, no credentials / 具体有界变更，不含凭据 | required / 必填 |
| `scope` | Exact files or directories ending in `/`, relative to repo root / 精确的文件或以 `/` 结尾的目录，相对于仓库根 | required / 必填 |
| `acceptance` | Observable outcomes / 可观察的结果 | required / 必填 |
| `preflight_verifiers` | Host checks that must pass before the worker / worker 运行前必须通过的宿主检查 | `[]` |
| `acceptance_verifiers` | Host checks for post-worker behavior / worker 运行后的宿主行为检查 | required / 必填 |
| `verifier_paths` | Trusted verifier files workers must not modify / worker 不得修改的受信检查文件 | optional / 可选 |
| `traits` | Six routing booleans (`bounded`, `verifiable`, `independent`, `dependency_stable`, `repetitive`, `context_heavy`) / 六个路由布尔值 | required / 必填 |
| `blockers` | Hard blockers such as `secrets`, `deployment`, `destructive`, `external_side_effects`, `policy_decision`, `unverifiable` / 硬性阻断项 | `[]` |
| `depends_on` | Other task ids that prevent automatic parallel scheduling / 阻止自动并行调度的其他任务 id | `[]` |
| `allow_pro` | Permit at most one evidence-backed Pro retry / 允许至多一次有证据支持的 Pro 重试 | `false` |
| `model_policy` | `flash-first` or `pro-only`; `pro-only` invokes `deepseek-v4-pro` directly and only / `flash-first` 或 `pro-only`；`pro-only` 直接且仅调用 `deepseek-v4-pro` | `flash-first` |
| `allow_noop` | Accept a verified empty patch only for an explicitly observational task / 仅对明确的观察性任务接受已验证的空补丁 | `false` |
| `task_timeout_seconds` | Per-attempt timeout (1–3600) / 每次尝试的超时（1–3600） | `600` |
| `max_provider_requests` | Provider request cap per attempt (1–100) / 每次尝试的提供商请求上限（1–100） | `24` |
| `max_model_output_tokens` | Output cap per request (512–32768) / 每次请求的输出上限（512–32768） | `8192` |
| `max_changed_files` | Changed file count cap (1–10000) / 更改文件数量上限（1–10000） | `200` |
| `max_changed_bytes` | Resulting file byte cap / 结果文件字节上限 | `20971520` (20 MiB) |
| `max_patch_bytes` | Patch byte cap / 补丁字节上限 | `41943040` (40 MiB) |

Each verifier has an `argv` string list executed without a shell, optional `cwd`, and `timeout_seconds`. `{python}` means the same Python interpreter running the router. Do not put secrets in argv.

每个检查器都有不带 shell 执行的 `argv` 字符串列表、可选的 `cwd` 和 `timeout_seconds`。`{python}` 表示运行路由器的同一个 Python 解释器。不要在 argv 中放入密钥。

## Review flow / 审查流程

1. Read the route result, changed code, and patch against the contract, scope, and acceptance.
2. Treat passing verifiers as evidence, not automatic authorization for unrelated work.
3. Run `integrate --check` before `integrate --apply`; apply only after your own review.
4. Run combined tests and inspect the final diff after integration. Distinguish local/offline tests from a live DeepSeek run.

1. 根据合同、范围和验收，阅读路由结果、更改的代码和补丁。
2. 将通过的检查视为证据，而不是对无关工作的自动授权。
3. 在 `integrate --apply` 之前运行 `integrate --check`；仅在自行审查后应用。
4. 集成后运行组合测试并检查最终差异。区分本地/离线测试与实际的 DeepSeek 运行。

## Troubleshooting / 故障排查

| Symptom / 症状 | Likely cause / 可能原因 | Fix / 处理 |
|---|---|---|
| `Dedicated runtime is missing` | `install_runtime.py` was not run, or the skill moved / 未运行 `install_runtime.py`，或技能目录已移动 | Run `python scripts/install_runtime.py` from the skill directory / 在技能目录中运行 `python scripts/install_runtime.py` |
| `doctor --online` reports `ready_for_live_attempt: false` | Missing Python/Git/shell, SDK incompatible, no key, or stale Flash capability / 缺少 Python/Git/shell、SDK 不兼容、没有密钥或 Flash 能力过期 | Read the JSON fields and fix the first false item, then rerun `python scripts/run.py doctor --online` / 阅读 JSON 字段并修复第一个 false 项，然后重新运行 `python scripts/run.py doctor --online` |
| `model_discovery_error` | Network/proxy failure or invalid `DEEPSEEK_BASE_URL` / 网络/代理故障或 `DEEPSEEK_BASE_URL` 无效 | Verify network, endpoint, and key; rerun `doctor --online` / 检查网络、端点和密钥，然后重新运行 `doctor --online` |
| Windows configure reports `DeepSeek rejected this key` | Invalid key / 密钥无效 | Check the key at the official DeepSeek console; it was not saved / 在 DeepSeek 官方控制台检查密钥；该密钥不会被保存 |
| `integrate` reports base or hash mismatch | Patch changed, wrong base, or overlapping scopes / 补丁已更改、base 错误或范围重叠 | Stop and resolve/rebase/reverify in Codex; never edit the recorded hash / 在 Codex 中停止并解决/变基/重新验证；切勿编辑记录的哈希 |
| Stale lock or worktree after an interrupted run / 中断后出现残留锁或工作树 | Interrupted router process / 路由器进程被中断 | Inspect the recorded PID and Git worktree inventory; remove only confirmed stale resources from that run / 检查记录的 PID 和 Git worktree 清单；只移除经确认的该运行残留资源 |

## Security limitations / 安全限制

Read [SECURITY.md](SECURITY.md) before using the skill. The DeepSeek worker uses the official `sdk-minimal` profile with full local process access. A Git worktree is not a security sandbox. Scope checks are post-run checks, not access control. The host proxy holds the real provider key, forces the assigned model, and caps requests and output tokens, but it does not restrict access to other OS-visible files. Only use trusted, non-sensitive repositories in an appropriately isolated execution environment. Keep secrets, deployments, destructive actions, external mutations, and policy decisions in Codex. Use a restricted VM or container when real isolation is required.

使用前请阅读 [SECURITY.md](SECURITY.md)。DeepSeek worker 使用官方 `sdk-minimal` 配置，拥有完整的本地进程访问权限。Git worktree 不是安全沙箱。范围检查是事后检查，不是访问控制。宿主代理持有真实提供商密钥，强制使用指定模型，并限制请求和输出令牌，但不会限制对操作系统可见的其他文件的访问。仅在适当隔离的执行环境中使用受信任、非敏感的仓库。将秘密、部署、破坏性操作、外部变更和策略决定保留在 Codex 中。需要真正隔离时，请使用受限的虚拟机或容器。

## Offline tests / 离线测试

Offline tests do not call DeepSeek and do not require an API key. They exercise router logic only; they do not prove the packaged live runtime works.

离线测试不会调用 DeepSeek，也不需要 API 密钥。它们只测试路由器逻辑，不能证明打包的在线运行时可用。

```bash
python -B -m unittest discover -s tests -v
```

## License / 许可证

MIT

See [SKILL.md](SKILL.md) for the agent workflow and `references/` for contracts, routing, escalation, runtime, and integration details.

有关代理工作流，请参阅 [SKILL.md](SKILL.md)；有关合同、路由、升级、运行时和集成细节，请参阅 `references/`。
