# Smart DeepSeek Router Usage / 使用手册

This manual complements [README.md](../README.md) and covers Smart DeepSeek Router v0.11.0 operations.

本手册是 [README.md](../README.md) 的操作补充，适用于 Smart DeepSeek Router v0.11.0。

## 1. Operating model / 运行模型

Astra inspects the repository, resolves architecture and safety decisions, creates reviewed contracts, assigns each independent task directly to one model, reviews host evidence, and controls integration.

Astra 检查仓库，处理架构与安全决策，创建受审合同，将每个独立任务直接分配给一个模型，复核宿主证据并控制集成。

| Alias / 别名 | Worker / 模型 | Intended use / 用途 |
|---|---|---|
| `flash` | discovered `deepseek-flash` | repetitive, simple, bounded work / 重复、简单、有界工作 |
| `pro` | discovered `deepseek-v4-pro` | context-heavy bounded implementation / 上下文较重的有界实现 |
| `luna` | `gpt-5.6-luna` | small reasoning or repair / 小型推理或修复 |
| `terra` | `gpt-5.6-terra` | medium implementation and debugging / 中等实现与调试 |
| `sol` | `gpt-5.6-sol` | complex cross-module work / 复杂跨模块工作 |

Assignment is direct. `flash-first` and `pro-only` remain accepted only for legacy contract compatibility; `auto` is the normalized contract default. Orchestration tasks explicitly name their model and do not escalate through the ladder.

模型采用直接分配。`flash-first` 和 `pro-only` 仅为旧合同兼容保留；规范合同默认使用 `auto`。调度任务显式指定模型，不会沿模型阶梯逐级升级。

## 2. Safety rules / 安全规则

- For `orchestrate`, use either a clean committed Git root or an ordinary directory. Ordinary directories are automatically mirrored into the run directory.
- Put every new run directory outside the repository.
- Delegate only authorized, bounded, independently verifiable work.
- Keep secrets, deployment, destructive actions, external side effects, and policy decisions in Astra.
- Treat worker prose as untrusted until host verification and patch review pass.
- Worktrees isolate Git state; they are not OS sandboxes.

- `orchestrate` 可以使用干净且已有提交的 Git 根目录或普通目录；普通目录会自动镜像到运行目录。
- 每个新运行目录都放在仓库之外。
- 只委派已授权、边界明确且可以独立验证的工作。
- 秘密、部署、破坏性操作、外部副作用和策略决定由 Astra 处理。
- 宿主验证和补丁审查通过前，不信任 worker 的文字声明。
- worktree 只隔离 Git 状态，不是操作系统沙箱。

Read [SECURITY.md](../SECURITY.md) before live use.

真实使用前请阅读 [SECURITY.md](../SECURITY.md)。

## 3. Setup and readiness / 配置与就绪检查

```powershell
python scripts\install_runtime.py
python scripts\run.py configure --state "$env:TEMP\smart-deepseek-router-config.json"
python scripts\run.py doctor --online
```

On Linux/macOS, provide `DEEPSEEK_API_KEY` through a secure environment or secret manager. Live execution requires Python 3.10+, Git, a platform shell, local Claude Code CLI, DeepSeek credentials, the compatibility runtime, and current model discovery.

在 Linux/macOS 上，通过安全环境或秘密管理器提供 `DEEPSEEK_API_KEY`。真实执行需要 Python 3.10+、Git、平台 shell、本地 Claude Code CLI、DeepSeek 凭据、兼容运行时和当前模型发现。

DeepSeek workers use the local Claude Code CLI through the Anthropic-compatible endpoint. The parent proxy holds the real key, supplies a one-time loopback token, forces the model, and caps requests/output. Codex workers use a temporary `CODEX_HOME` containing authentication only, so user config, rules, plugins, and Skills are not inherited.

DeepSeek worker 通过本地 Claude Code CLI 调用 Anthropic 兼容接口。父代理保留真实密钥，提供一次性回环令牌，强制模型并限制请求/输出。Codex worker 使用只包含登录凭据的临时 `CODEX_HOME`，不会继承用户配置、规则、插件和 Skills。

## 4. Contract schema / 合同结构

```json
{
  "schema_version": 2,
  "id": "update-parser",
  "objective": "Fix the parser regression and focused tests.",
  "scope": ["src/parser.py", "tests/test_parser.py"],
  "acceptance": ["Focused parser tests pass."],
  "preflight_verifiers": [],
  "acceptance_verifiers": [
    {
      "argv": ["{python}", "-m", "unittest", "tests.test_parser"],
      "timeout_seconds": 120
    }
  ],
  "verifier_paths": [],
  "allow_noop": false,
  "model_policy": "auto",
  "task_timeout_seconds": 600,
  "max_provider_requests": 24,
  "max_model_output_tokens": 8192,
  "max_changed_files": 20,
  "max_changed_bytes": 1048576,
  "max_patch_bytes": 2097152
}
```

| Field / 字段 | Meaning / 含义 |
|---|---|
| `id` | unique lowercase task ID / 唯一小写任务 ID |
| `objective` | one concrete bounded outcome / 一个具体且有界的结果 |
| `scope` | exact writable files or `/`-terminated directories / 精确可写文件或以 `/` 结尾的目录 |
| `acceptance` | observable outcomes / 可观察结果 |
| `acceptance_verifiers` | no-shell argv checks run by the host / 宿主执行的无 shell argv 检查 |
| `verifier_paths` | trusted verifier files workers cannot modify / worker 不得修改的受信验证文件 |
| `model_policy` | normally `auto`; legacy values are compatibility only / 通常为 `auto`，旧值只用于兼容 |
| `task_timeout_seconds` | worker wall-clock limit, 1–3600 / worker 总时限，1–3600 秒 |
| `max_provider_requests` | DeepSeek request cap, 1–100 / DeepSeek 请求上限，1–100 |
| `max_model_output_tokens` | per-request output cap, 512–32768 / 单请求输出上限，512–32768 |
| `max_changed_files` | maximum changed file count / 最大变更文件数 |
| `max_changed_bytes` | maximum resulting changed bytes / 最大结果变更字节数 |
| `max_patch_bytes` | maximum exported patch size / 最大导出补丁大小 |

Use repository-relative POSIX paths even on Windows. `{python}` resolves to the router interpreter. Never put secrets in verifier argv.

即使在 Windows 上，合同也使用相对于仓库的 POSIX 路径。`{python}` 解析为路由器解释器。不要在验证命令 argv 中放入秘密。

## 5. Plan candidates / 规划候选任务

Planning traits are `bounded`, `verifiable`, `independent`, `dependency_stable`, `repetitive`, and `context_heavy`. Hard blockers include `secrets`, `deployment`, `destructive`, `external_side_effects`, `policy_decision`, and `unverifiable`.

规划特征包括 `bounded`、`verifiable`、`independent`、`dependency_stable`、`repetitive` 和 `context_heavy`。硬阻断项包括 `secrets`、`deployment`、`destructive`、`external_side_effects`、`policy_decision` 和 `unverifiable`。

```powershell
python scripts\run.py plan --plan references\example-plan.json --out-dir C:\router-output\planning-001
```

Review `routing.json` and every generated `contracts/<id>.json` before execution.

执行前检查 `routing.json` 和每个生成的 `contracts/<id>.json`。

## 6. Parallel orchestration / 并行调度

Tasks require unique IDs, explicit model aliases, reviewed contracts, resolved dependencies/blockers, and non-overlapping scopes.

任务必须具有唯一 ID、显式模型别名、受审合同、已解决的依赖/阻断项以及互不重叠的范围。

```json
{
  "tasks": [
    {
      "id": "docs-cleanup",
      "model": "flash",
      "prompt": "Apply only the reviewed documentation contract.",
      "contract": "contracts/docs-cleanup.json"
    },
    {
      "id": "parser-repair",
      "model": "terra",
      "prompt": "Apply only the reviewed parser contract.",
      "contract": "contracts/parser-repair.json"
    }
  ]
}
```

```powershell
python scripts\run.py orchestrate `
  --repo C:\projects\repo-or-folder `
  --plan C:\router-input\orchestration-plan.json `
  --run-dir C:\router-output\run-001 `
  --max-workers 3
```

The orchestrator validates all contracts/scopes first. A non-Git source is filtered into `source-mirror` with a hashed `source-manifest.json`; sensitive/generated paths are excluded and unsafe symlinks are rejected. It then creates one detached worktree per task at the same base commit, runs up to five tasks concurrently, verifies results, exports patches, and sorts collected results by task ID.

调度器先验证所有合同和范围。非 Git 源会被过滤到 `source-mirror`，同时生成带哈希的 `source-manifest.json`；敏感/生成目录会被排除，不安全符号链接会被拒绝。随后它基于同一提交为每个任务创建独立工作树，最多并发运行五个任务，然后验证结果、导出补丁并按任务 ID 排序汇总。

## 7. Direct route and dispatch / 单任务路由与分派

```powershell
python scripts\run.py route `
  --workdir C:\projects\task-worktree `
  --contract C:\router-input\task.json `
  --run-dir C:\router-output\task-001 `
  --result-out C:\router-output\task-001\route-result.json

python scripts\run.py dispatch `
  --workdir C:\projects\repo-or-folder `
  --plan C:\router-input\candidate-plan.json `
  --run-dir C:\router-output\dispatch-001 `
  --max-workers 3
```

Do not run multiple router instances against the same repository; repository locking rejects it.

不要对同一仓库同时运行多个路由器实例；仓库锁会主动拒绝这种情况。

## 8. Review results / 复核结果

```text
orchestration-result.json
tasks/<id>/route-result.json
tasks/<id>/result.patch
tasks/<id>/<model>/process-result.json
worktrees/<id>/
```

Review in this order:

按以下顺序复核：

1. Parent `status`, `parallel`, and `primary_unchanged`.
2. Every task status and assigned model.
3. Verifier exit codes and implementation-failure flags.
4. `changed_files`, byte limits, and contract scope.
5. Retained worktree and `result.patch`.
6. Recorded base commit and patch SHA-256.

1. 父结果中的 `status`、`parallel` 和 `primary_unchanged`。
2. 每个任务的状态和指定模型。
3. 验证器退出码和实现失败标记。
4. `changed_files`、字节限制和合同范围。
5. 保留的工作树和 `result.patch`。
6. 记录的基础提交和补丁 SHA-256。

Worker prose is never completion evidence by itself.

Worker 的文字声明本身永远不能作为完成证据。

## 9. Token collection / Token 采集

For Codex, parse the last `type: "turn.completed"` JSON object from `process-result.json.output`. Its `usage` contains `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, and `reasoning_output_tokens`. Cached input and reasoning output are subsets; do not add them twice.

对于 Codex，从 `process-result.json.output` 中解析最后一个 `type: "turn.completed"` JSON 对象。其 `usage` 包含输入、缓存输入、缓存写入、输出和推理输出。缓存输入和推理输出属于子集，不要重复相加。

For DeepSeek, parse `attempts[0].worker.cli_output` as JSON and read `modelUsage`. Comparable processed tokens equal `inputTokens + cacheReadInputTokens + cacheCreationInputTokens + outputTokens`. Provider cost appears only when supplied upstream. Do not infer Astra usage because the parent interface does not expose exact coordinator tokens.

对于 DeepSeek，将 `attempts[0].worker.cli_output` 解析为 JSON 并读取 `modelUsage`。可比处理总量为 `inputTokens + cacheReadInputTokens + cacheCreationInputTokens + outputTokens`。只有上游提供时才会记录成本。不要推测 Astra 用量，因为父接口不会暴露协调器的精确 Token。

## 10. Integration / 集成

```powershell
python scripts\run.py integrate `
  --workdir C:\projects\repo-or-folder `
  --patch C:\router-output\run-001\tasks\docs-cleanup\result.patch `
  --patch C:\router-output\run-001\tasks\parser-repair\result.patch `
  --check

python scripts\run.py integrate `
  --workdir C:\projects\clean-repo `
  --patch C:\router-output\run-001\tasks\docs-cleanup\result.patch `
  --patch C:\router-output\run-001\tasks\parser-repair\result.patch `
  --apply
```

For Git, `--check` validates the clean recorded base. For an ordinary directory it validates the source manifest, rebuilds a candidate mirror, and checks all patches there. `--apply` rechecks for concurrent source edits and writes only validated changed files. Patch hashes, scopes, and overlaps are checked in both modes.

对于 Git，`--check` 验证干净且匹配的基础提交；对于普通目录，它验证源清单、重建候选镜像并在其中检查全部补丁。`--apply` 会再次检查并发编辑，只写入通过验证的变更文件。两种模式都会校验补丁哈希、范围和重叠。

## 11. Failure handling / 失败处理

- Infrastructure errors, missing credentials/models, timeouts, dependency failures, permission errors, scope violations, and verifier failures do not silently switch models.
- Every retry uses a new run directory.
- Failed worktrees remain for inspection.
- Never edit recorded hashes to bypass validation.
- Remove stale worktrees only after matching their path and owning run.

- 基础设施错误、凭据/模型缺失、超时、依赖失败、权限错误、范围违规和验证失败不会静默切换模型。
- 每次重试使用新的运行目录。
- 失败工作树会保留以供检查。
- 不要修改记录哈希来绕过验证。
- 只有在核对路径和所属运行后才能移除失效工作树。

## 12. Development verification / 开发验证

```powershell
python -B -m unittest discover -s tests -v
python scripts\run.py doctor --online
```

Offline tests verify routing, contracts, proxy limits, worktree isolation, patch integrity, and orchestration. They do not contact DeepSeek. Report a live route separately.

离线测试验证路由、合同、代理限制、工作树隔离、补丁完整性和调度，不会连接 DeepSeek。真实路由必须单独报告。
