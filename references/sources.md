# Upstream provenance and compatibility

Inspected on 2026-09-13: the official [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) source archive, revision `c291e7961a515f6d7af9304e7fd1d257929aef26` (GitHub archive comment).

Primary source references:

- [Python SDK API source](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/python/sdk/src/deepseek_harness/api.py): configuration fields, context-manager lifecycle, run method, and `RunResult.finish_reason`.
- [Python SDK client](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/python/sdk/src/deepseek_harness/client.py): explicit home, environment inheritance, stdio runtime launch, bounded initialization/shutdown.
- [SDK README](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/python/sdk/README.md): official package names, runtime lifecycle, profiles, result semantics.
- [Minimal profile README](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/packages/bundle/sdk-minimal/README.md) and [composition](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/packages/bundle/sdk-minimal/cordis.patch.yml): platform shells, environment credential, JSONL persistence, no managed credentials, full local access, no built-in subagents.
- [Official safety guidance](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/SAFETY.md): Harness agents can execute code and should be run only in trusted, isolated environments with reviewed credentials and permissions.

This skill's Python routing/planning/Git orchestration code is newly written against those public interfaces. No upstream source is bundled. The scoring weights, contract schema, host-verification policy, patch hashes, and dispatch limits are local design choices based on the user's supplied SKILL.md, not official DeepSeek functionality.

Validation: `python -B -m unittest discover -s <skill-dir>/tests -v` exercises disposable real Git worktrees and a fake loopback provider with no paid calls. It covers binary/new-file patches, strict schema handling, dependency cycles, empty changes, resource limits, primary ignored-file monitoring, credential proxying, assigned-model enforcement, and escalation failure paths. The source-level SDK adapter is also checked against the inspected public SDK. An actual SDK/runtime installation and live DeepSeek attempt must be separately reported as such.
