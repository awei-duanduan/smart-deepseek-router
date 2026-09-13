# Smart DeepSeek Router

A DeepSeek-first Codex skill for bounded repository implementation. DeepSeek handles scoped coding and repository investigation while Codex keeps task contracts, architecture decisions, host verification, patch review, and integration control.

The router provides strict task contracts, isolated Git worktrees for parallel tasks, dynamic Flash/Pro capability discovery, a loopback credential proxy, request and output limits, host-run acceptance checks, and reviewed binary patch export.

## Requirements

- Codex with local skill support
- Python 3.10 or newer
- Git
- PowerShell on Windows, or Bash on Linux/macOS
- A DeepSeek API key

DeepSeek Harness currently runs agents with the permissions of the local process. Read [SECURITY.md](SECURITY.md) before using the skill.

## Install

Clone the repository into your Codex skills directory:

```bash
git clone https://github.com/awei-duanduan/smart-deepseek-router.git "$HOME/.codex/skills/smart-deepseek-router"
cd "$HOME/.codex/skills/smart-deepseek-router"
python scripts/install_runtime.py
```

If `CODEX_HOME` is set, clone into `$CODEX_HOME/skills/smart-deepseek-router` instead.

Set `DEEPSEEK_API_KEY` in your local secure environment. Windows users may alternatively run the local DPAPI form:

```powershell
python scripts/run.py configure --state "$env:TEMP\smart-deepseek-router-config.json"
```

Then check runtime and provider capabilities:

```bash
python scripts/run.py doctor --online
```

## Use in Codex

Invoke the skill explicitly:

```text
Use $smart-deepseek-router to implement this bounded change and verify it with the repository tests: ...
```

Allow one evidence-backed Pro retry only when desired:

```text
Use $smart-deepseek-router for this task. If Flash completes but the host acceptance check shows a specific implementation failure, allow one Pro retry.
```

For an explicit Pro-only task, set the contract policy to `pro-only` so the router invokes `deepseek-v4-pro` first and only, with no Flash attempt:

```text
Use $smart-deepseek-router with DeepSeek Pro only for this bounded repository task: ...
```

```json
"model_policy": "pro-only"
```

The skill also supports automatic selection when Codex recognizes a suitable bounded and testable repository task.

## Development

Offline tests do not call DeepSeek or require an API key:

```bash
python -B -m unittest discover -s tests -v
```

See [SKILL.md](SKILL.md) for the agent workflow and `references/` for contracts, routing, escalation, runtime, and integration details.

## License

MIT
