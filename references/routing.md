# DeepSeek-first routing heuristic

This transparent heuristic favors DeepSeek for implementation work when Codex can bound the write scope and verify the result. It is a local policy, not an upstream DeepSeek algorithm or a calibrated cost/performance predictor.

| Trait set to true | Points | Meaning |
|---|---:|---|
| `bounded` | +3 | Exact write scope and one coherent outcome |
| `verifiable` | +3 | Host can independently check the result |
| `independent` | +2 | No dependency on another candidate's changes |
| `dependency_stable` | +2 | No dependency installation/version or shared contract changes needed |
| `repetitive` | +1 | Routine repeated changes with little architecture judgment |
| `context_heavy` | +1 | Requires substantial repository reading that DeepSeek can perform inside a bounded, verifiable contract |

Delegate when `bounded` and `verifiable` are true, score >= 6, and blockers are empty. The score is a triage aid; Codex still owns factual classification. Keep architecture and external actions in Codex, then delegate the resulting implementation slice instead of duplicating repository analysis in both models.

Allowed hard blockers: `secrets`, `deployment`, `destructive`, `external_side_effects`, `policy_decision`, `unverifiable`. These always keep a candidate in Codex, regardless of score. A syntactically valid contract is not proof that a task is safe; the planner must accurately classify its contents.

Automatic dispatch additionally requires `independent`, `dependency_stable`, no `depends_on`, and non-overlapping write scopes. Different filenames alone do not imply independence: shared APIs, schemas, configuration, dependency locks, and generated resources can create semantic conflicts. Keep such work sequential or in Codex.
