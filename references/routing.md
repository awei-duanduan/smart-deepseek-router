# Local v0.5 heuristic

The supplied v0.3 file did not include its scoring implementation. This transparent heuristic is a local implementation choice, not an upstream DeepSeek algorithm or a calibrated cost/performance predictor.

| Trait set to true | Points | Meaning |
|---|---:|---|
| `bounded` | +3 | Exact write scope and one coherent outcome |
| `verifiable` | +3 | Host can independently check the result |
| `independent` | +2 | No dependency on another candidate's changes |
| `dependency_stable` | +2 | No dependency installation/version or shared contract changes needed |
| `repetitive` | +1 | Routine repeated changes with little architecture judgment |
| `context_heavy` | -2 | Requires broad repository/product knowledge to implement |

Delegate only if `bounded` and `verifiable` are true, score >= 6, and blockers are empty. The score is a triage aid; Codex still owns factual classification. Not every high-scoring tiny edit benefits from another model call.

Allowed hard blockers: `secrets`, `deployment`, `destructive`, `external_side_effects`, `policy_decision`, `unverifiable`. These always keep a candidate in Codex, regardless of score. A syntactically valid contract is not proof that a task is safe; the planner must accurately classify its contents.

Automatic dispatch additionally requires `independent`, `dependency_stable`, no `depends_on`, and non-overlapping write scopes. Different filenames alone do not imply independence: shared APIs, schemas, configuration, dependency locks, and generated resources can create semantic conflicts. Keep such work sequential or in Codex.
