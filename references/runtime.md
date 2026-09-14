# Runtime and Windows support

Run `python <skill-dir>/scripts/run.py doctor --online` before the first live route and after provider/model changes. The wrapper selects the dedicated runtime and, on Windows, loads the current user's DPAPI-encrypted key into the router process. Doctor never prints the key or installs anything. Without `--online` it uses a model capability cache valid for 24 hours; with `--online` it refreshes the official model list and records the selected Flash/Pro ids. A positive report is not a billing or isolation guarantee.

For live routing, DeepSeek workers use the local Claude Code CLI and DeepSeek's Anthropic-compatible endpoint (`https://api.deepseek.com/anthropic`). The parent proxy injects a per-attempt `ANTHROPIC_API_KEY`, forces the assigned model, and caps requests/output. The legacy `deepseek-harness-sdk` remains installed for compatibility diagnostics but is not the live worker path. Verify `claude --version` before a live route.

If the user requests runtime setup, use the included installer. It creates a dedicated virtual environment outside the skill directory and installs the compatibility-tested SDK/runtime version:

```text
python <skill-dir>/scripts/install_runtime.py
python <skill-dir>/scripts/run.py doctor
```

Use `scripts/run.py` for router commands so the same Python interpreter and configured credential are selected. Keep virtual environments outside repositories. The default installer pins SDK/runtime `0.1.5rc1`, the compatibility-tested pre-release. Review upstream changes and rerun all tests before selecting another version with `install_runtime.py --version`.

The inspected official minimal profile selects persistent PowerShell on Windows and Bash on Linux/macOS. Ensure the relevant shell is available. The local scripts and Git tests support Windows and use argv-based subprocess execution. A full live runtime boot remains a separate check; a locally passing test suite does not prove the packaged runtime works on every platform.

Provide `DEEPSEEK_API_KEY` through a secure local environment configuration; never paste it into chat, write it into a plan, or put it on a command line. On Windows, `configure.py --state <private-status-file>` opens a short-lived loopback form and stores the key as `credential.dpapi`, encrypted for the current Windows user. The non-secret state records only success, timestamps, and returned model ids. The optional `DEEPSEEK_BASE_URL` selects an explicitly configured compatible endpoint and is part of the cache identity.

The SDK worker receives a small allowlisted environment plus a random per-attempt bearer token and a loopback provider URL. The parent router retains the real key. Its proxy accepts only the assigned model, caps provider requests and `max_tokens`, and does not log bodies. This limits ordinary credential exposure and accidental model switching. The full-access shell can still inspect process-accessible files or interfere with local processes, so this is not an OS security boundary. SDK-owned JSONL session logs remain in each attempt's `home` directory; treat run directories as private working data.

When the SDK is absent, planning, patch review, and offline tests still work. Execution exits with a setup message. There is no guessed `dsh --headless` CLI syntax: exact model selection and finish-reason handling use the verified Python SDK.
