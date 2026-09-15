# Smart DeepSeek Router / 智能 DeepSeek 路由器

> Astra-led planning and review, direct model assignment, parallel Codex/DeepSeek workers, host verification, and explicit patch integration.  
> 由 Astra 负责规划与复核，直接分配模型，并行运行 Codex/DeepSeek worker，由宿主验证，最后显式集成补丁。

Smart DeepSeek Router is a Codex Skill for bounded, testable repository work. Astra keeps control of architecture, risk, contracts, verification, and final synthesis while implementation slices go directly to the least expensive capable model.

Smart DeepSeek Router 面向边界清晰、可以测试的仓库任务。Astra 保留架构、风险、合同、验证和最终汇总控制权，将实现切片直接交给能够胜任的最低成本模型。

Current release / 当前版本：**v0.11.0**

## Architecture / 工作架构

```text
User request / 用户请求
          |
          v
Astra: inspect -> split -> contract -> assign
Astra：检查 -> 拆分 -> 合同 -> 分配
          |
          +---------------- parallel / 并行 ----------------+
          |          |          |          |                |
        Flash       Pro        Luna       Terra             Sol
          |          |          |          |                |
          +----------+----------+----------+----------------+
                                 |
                       isolated Git worktrees
                         独立 Git 工作树
                                 |
                    host verification + patch export
                       宿主验证 + 补丁导出
                                 |
                    Astra review and synthesis
                         Astra 复核与汇总
                                 |
                      explicit integration only
                           仅显式集成
```

This is **direct assignment**, not a Flash-first retry chain. Astra classifies independent tasks before execution, assigns each task once, and launches eligible tasks concurrently.

这是**直接分配**，不是 Flash 优先的逐级重试链。Astra 在执行前分类独立任务，每个任务直接选择一次模型，并将符合条件的任务并行启动。

| Task profile / 任务类型 | Executor / 执行模型 |
|---|---|
| Repetitive edits, simple inspection, routine tests / 重复编辑、简单检查、常规测试 | DeepSeek Flash |
| Context-heavy but bounded implementation / 上下文较重但边界明确的实现 | DeepSeek Pro |
| Simple reasoning or small repair / 简单推理或小型修复 | Luna |
| Medium implementation, debugging, test design / 中等实现、调试、测试设计 | Terra |
| Complex cross-module work or substantial uncertainty / 复杂跨模块工作或较高不确定性 | Sol |
| Architecture, security, irreversible decisions, recovery / 架构、安全、不可逆决策、恢复 | Astra directly / Astra 直接处理 |

Secrets, deployment, destructive actions, policy decisions, unverifiable work, and external side effects always stay with Astra.

秘密、部署、破坏性操作、策略决定、不可验证工作和外部副作用始终由 Astra 处理。

## Core capabilities / 核心能力

- Reviewed JSON contracts with exact write scope and executable acceptance checks.
- Independent detached Git worktrees for concurrent workers.
- Direct support for `flash`, `pro`, `luna`, `terra`, and `sol`.
- DeepSeek through the local Claude Code CLI and Anthropic-compatible endpoint.
- Loopback credential proxy: the parent keeps the real key, forces the assigned model, and caps requests/output.
- Host verification, scope/size audits, binary patch export, and hash-bound integration.
- Parent collection through `orchestration-result.json`.

- 使用精确写入范围和可执行验收检查的受审 JSON 合同。
- 为并发 worker 创建独立的分离 Git worktree。
- 直接支持 `flash`、`pro`、`luna`、`terra` 和 `sol`。
- 通过本地 Claude Code CLI 和 Anthropic 兼容接口访问 DeepSeek。
- 回环凭据代理由父进程保留真实密钥，强制指定模型并限制请求数和输出量。
- 宿主验证、范围/大小审计、二进制补丁导出和哈希绑定集成。
- 父任务通过 `orchestration-result.json` 收集结果。

## Security boundary / 安全边界

**A Git worktree is not an OS sandbox.** The DeepSeek worker has the local process's OS-visible access. Post-run scope checks detect out-of-contract changes but cannot prevent reads or process interaction. Use only trusted, non-sensitive repositories in an isolated machine, VM, or container. Read [SECURITY.md](SECURITY.md).

**Git worktree 不是操作系统沙箱。** DeepSeek worker 拥有本地进程可见的系统访问权限。事后范围检查能发现超出合同的修改，但不能阻止读取或进程交互。请只在隔离的电脑、虚拟机或容器中处理受信任且不敏感的仓库。请阅读 [SECURITY.md](SECURITY.md)。

Never put a real API key in chat, plans, contracts, repository files, or command history.

切勿把真实 API 密钥放进聊天、计划、合同、仓库文件或命令历史。

## Requirements / 前置条件

- Codex desktop/CLI with local Skill support / 支持本地 Skill 的 Codex 桌面端或 CLI
- Python 3.10+, Git, and a platform shell / Python 3.10+、Git 和平台 shell
- Local Claude Code CLI for live DeepSeek workers / 真实 DeepSeek worker 需要本地 Claude Code CLI
- DeepSeek API key and network access for live execution / 真实执行需要 DeepSeek API 密钥和网络

## Installation / 安装

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
Set-Location "$SkillsDir\smart-deepseek-router"
python scripts\install_runtime.py
```

`install_runtime.py` creates the compatibility runtime outside the Skill directory. Always use `scripts/run.py` for router commands.

`install_runtime.py` 会在 Skill 目录之外创建兼容运行时。后续路由命令始终通过 `scripts/run.py` 执行。

## Configure the DeepSeek key / 配置 DeepSeek 密钥

Linux/macOS:

```bash
export DEEPSEEK_API_KEY="<your-deepseek-api-key>"
```

Windows recommends a short-lived loopback form that stores the key with DPAPI and never prints it:

Windows 推荐使用短期有效的本地回环页面，通过 DPAPI 加密保存密钥，且不会打印密钥：

```powershell
python scripts\run.py configure --state "$env:TEMP\smart-deepseek-router-config.json"
```

Optional `DEEPSEEK_ANTHROPIC_BASE_URL` selects another explicitly trusted Anthropic-compatible endpoint.

可选的 `DEEPSEEK_ANTHROPIC_BASE_URL` 可指向另一个明确受信任的 Anthropic 兼容端点。

## Readiness check / 就绪检查

```powershell
python scripts\run.py doctor --online
```

Run it before the first live task and after provider/model changes. `ready_for_live_attempt: true` confirms prerequisites and discovery, not account balance or OS isolation.

在第一次真实任务前及提供商/模型变化后运行。`ready_for_live_attempt: true` 表示依赖和模型发现正常，不代表余额或操作系统隔离得到保证。

## Quick start in Codex / 在 Codex 中快速使用

```text
Use $smart-deepseek-router. Let Astra split this repository task into independent,
testable contracts, assign each task directly to the lowest capable model, run
eligible tasks in parallel, verify every patch, and summarize the evidence: ...
```

```text
使用 $smart-deepseek-router。让 Astra 将此仓库任务拆成独立且可测试的合同，
按照难度直接分配给能够胜任的最低成本模型，并行运行符合条件的任务，
验证每个补丁并汇总证据：……
```

`orchestrate` accepts a clean committed Git root or an ordinary directory. Ordinary directories are copied into a filtered temporary Git mirror under the run directory; the original is not modified during worker execution. Every run directory must be new and outside the source.

`orchestrate` 可以接收干净且已有提交的 Git 根目录，也可以接收普通目录。普通目录会被复制为运行目录内的过滤式临时 Git 镜像；worker 执行期间不会修改原目录。每次运行目录必须是新的，并位于源目录之外。

## Parallel orchestration / 并行调度

Each task has a unique ID, an explicit model alias, and a reviewed contract. Scopes must not overlap.

每个任务包含唯一 ID、显式模型别名和受审合同，任务范围不得重叠。

```json
{
  "tasks": [
    {
      "id": "format-config",
      "model": "flash",
      "prompt": "Normalize config/defaults.json only.",
      "contract": {
        "schema_version": 2,
        "id": "format-config",
        "objective": "Normalize config/defaults.json without changing values.",
        "scope": ["config/defaults.json"],
        "acceptance": ["The JSON parses."],
        "acceptance_verifiers": [
          {"argv": ["{python}", "-c", "import json; json.load(open('config/defaults.json', encoding='utf-8'))"]}
        ]
      }
    },
    {
      "id": "repair-parser",
      "model": "terra",
      "prompt": "Repair the parser within the reviewed contract.",
      "contract": {
        "schema_version": 2,
        "id": "repair-parser",
        "objective": "Fix the parser regression and focused test.",
        "scope": ["src/parser.py", "tests/test_parser.py"],
        "acceptance": ["Focused parser tests pass."],
        "acceptance_verifiers": [
          {"argv": ["{python}", "-m", "unittest", "tests.test_parser"]}
        ]
      }
    }
  ]
}
```

Windows:

```powershell
python scripts\run.py orchestrate `
  --repo C:\path\to\repo-or-folder `
  --plan C:\path\to\orchestration-plan.json `
  --run-dir C:\path\outside-repo\router-run-001 `
  --max-workers 3
```

Linux/macOS:

```bash
python3 scripts/run.py orchestrate \
  --repo /path/to/repo-or-folder \
  --plan /path/to/orchestration-plan.json \
  --run-dir /path/outside-repo/router-run-001 \
  --max-workers 3
```

The parent writes `orchestration-result.json`, one task directory and worktree per worker, verification evidence, and exported `result.patch` files. Patches are never applied automatically.

父任务写入 `orchestration-result.json`、每个 worker 的任务目录和工作树、验证证据以及导出的 `result.patch`。补丁绝不会自动应用。

## Other commands / 其他命令

```bash
python scripts/run.py plan --plan references/example-plan.json --out-dir ../router-plan
python scripts/run.py route --workdir /path/to/worktree --contract ../router-plan/contracts/task.json --run-dir ../runs/task-001 --result-out ../runs/task-001/route-result.json
python scripts/run.py dispatch --workdir /path/to/clean-repo --plan ../candidate-plan.json --run-dir ../runs/dispatch-001 --max-workers 3
```

Check and apply reviewed patches explicitly:

显式检查并应用已经审查的补丁：

```powershell
python scripts\run.py integrate --workdir C:\path\to\repo-or-folder --patch C:\path\outside-source\router-run-001\tasks\task-id\result.patch --check
python scripts\run.py integrate --workdir C:\path\to\repo-or-folder --patch C:\path\outside-source\router-run-001\tasks\task-id\result.patch --apply
```

For Git sources, `--check` validates the base commit. For ordinary directories, it validates the recorded source manifest and checks patches in a fresh mirror. Both modes validate patch hashes and scope without modifying the source. `--apply` writes only reviewed files and does not commit; Astra then inspects the combined result and reruns tests.

对于 Git 源，`--check` 验证基础提交；对于普通目录，它验证源清单并在新镜像中检查补丁。两种模式都在不修改源目录的情况下验证补丁哈希和范围。`--apply` 只写入已审查文件且不提交；随后 Astra 检查组合结果并重新运行测试。

## Results and token accounting / 结果与 Token 统计

- `orchestration-result.json`: parent status, model assignment, worktrees, and `primary_unchanged`.  
  父任务状态、模型分配、工作树和 `primary_unchanged`。
- `tasks/<id>/route-result.json`: patch, changed files, verification, and provider telemetry.  
  补丁、变更文件、验证和提供商遥测。
- Codex `process-result.json`: raw JSONL containing `turn.completed.usage`.  
  Codex 原始 JSONL，包含 `turn.completed.usage`。
- DeepSeek `worker.cli_output`: result JSON containing `usage` and `modelUsage`.  
  DeepSeek 结果 JSON，包含 `usage` 和 `modelUsage`。

Codex cached input is a subset of `input_tokens`; do not add it twice. DeepSeek reports `inputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, and `outputTokens` separately; add all four for a comparable processed-token total. Reasoning output is a subset of Codex output. Exact Astra per-turn usage is not exposed to the parent task.

Codex 缓存输入已包含在 `input_tokens` 中，不要重复相加。DeepSeek 分别报告 `inputTokens`、`cacheReadInputTokens`、`cacheCreationInputTokens` 和 `outputTokens`，可比处理总量应将四者相加。推理输出是 Codex 输出的一部分。父任务无法读取 Astra 本轮的精确用量。

### Verified live smoke test / 已验证的真实冒烟测试

This 2026-09-15 five-file run validates routing and accounting paths; it is **not** a quality, speed, or price benchmark.

以下 2026-09-15 五文件运行用于验证路由和计量链路，**不是**质量、速度或价格基准。

| Model / 模型 | Result / 结果 | Input | Cached/read | Output | Comparable total / 可比总量 |
|---|---:|---:|---:|---:|---:|
| `deepseek-flash` | passed | 3,110 | 18,048 | 1,754 | 22,912 |
| `deepseek-v4-pro[1m]` | passed | 1,895 | 5,888 | 603 | 8,386 |
| `gpt-5.6-luna` | passed | 165,986 | 150,272 (subset / 子集) | 1,104 | 167,090 |
| `gpt-5.6-terra` | passed | 118,248 | 104,960 (subset / 子集) | 664 | 118,912 |
| `gpt-5.6-sol` | passed | 139,832 | 128,512 (subset / 子集) | 1,058 | 140,890 |

All five tasks ran concurrently, passed host verification, used separate worktrees, and left the primary repository unchanged.

五个任务并行运行，全部通过宿主验证，使用独立工作树，并保持主仓库不变。

## Troubleshooting / 故障排查

| Symptom / 症状 | Action / 处理 |
|---|---|
| `ready_for_live_attempt: false` | Fix the first false/missing doctor field, then rerun. / 修复 doctor 中第一个异常字段后重试。 |
| `model_discovery_error` | Check network, key, and endpoint. / 检查网络、密钥和端点。 |
| Codex timeout/reconnect / Codex 超时或重连 | Inspect `process-result.json`; retry with a new run directory after connectivity recovers. / 查看日志；网络恢复后用新运行目录重试。 |
| Scope/size violation / 范围或大小违规 | Do not integrate; inspect the worktree and contract. / 不要集成；检查工作树和合同。 |
| Base/hash mismatch / 基础或哈希不匹配 | Stop and reverify the original patch against its recorded base. / 停止并针对记录基础重新验证原始补丁。 |

See the detailed [usage manual](docs/USAGE.md), [SKILL.md](SKILL.md), and [SECURITY.md](SECURITY.md).

更多信息请参阅[详细使用手册](docs/USAGE.md)、[SKILL.md](SKILL.md) 和 [SECURITY.md](SECURITY.md)。

## Development / 开发验证

```powershell
python -B -m unittest discover -s tests -v
python scripts\run.py doctor --online
```

Offline tests do not call paid models and do not prove live provider availability. Report live tests separately.

离线测试不会调用付费模型，也不能证明提供商实时可用；真实调用必须单独报告。

## License / 许可证

[MIT](LICENSE)
