# DeepSeek-first routing heuristic

This transparent heuristic favors the lowest capable executor when Astra can bound the write scope and verify the result. It is a local policy, not an upstream DeepSeek or Codex algorithm or a calibrated cost/performance predictor.

| Trait set to true | Points | Meaning |
|---|---:|---|
| `bounded` | +3 | Exact write scope and one coherent outcome |
| `verifiable` | +3 | Host can independently check the result |
| `independent` | +2 | No dependency on another candidate's changes |
| `dependency_stable` | +2 | No dependency installation/version or shared contract changes needed |
| `repetitive` | +1 | Routine repeated changes with little architecture judgment |
| `context_heavy` | +1 | Requires substantial repository reading that DeepSeek can perform inside a bounded, verifiable contract |

Delegate when `bounded` and `verifiable` are true, score >= 6, and blockers are empty. The score is a triage aid; Astra still owns factual classification. Keep architecture and external actions in Astra, then delegate the resulting implementation slice instead of duplicating repository analysis across models.

## Cost-aware executor selection

Assign each independent task directly to the first tier that can safely complete it, then run eligible tasks in parallel:

| Condition | Tier |
|---|---|
| Routine, repetitive, bounded, independently verifiable | DeepSeek Flash |
| Context-heavy, bounded, independently verifiable | DeepSeek Pro |
| Small reasoning task needing a Codex model | Luna |
| Medium reasoning, debugging, or test-design task | Terra |
| Complex architecture, cross-module uncertainty, or difficult recovery | Sol |
| Security, irreversible decisions, policy, or unbounded ambiguity | Astra directly |

Do not run Flash and Pro serially for the same task as the normal path. DeepSeek Flash/Pro are the direct worker choices implemented by this router; Luna/Terra/Sol are Codex-side coordination or review tiers and require the host's model-selection mechanism. A retry or escalation after failure is an exceptional recovery decision, not part of ordinary routing.

Allowed hard blockers: `secrets`, `deployment`, `destructive`, `external_side_effects`, `policy_decision`, `unverifiable`. These always keep a candidate in Codex, regardless of score. A syntactically valid contract is not proof that a task is safe; the planner must accurately classify its contents.

Automatic dispatch additionally requires `independent`, `dependency_stable`, no `depends_on`, and non-overlapping write scopes. Different filenames alone do not imply independence: shared APIs, schemas, configuration, dependency locks, and generated resources can create semantic conflicts. Keep such work sequential or in Codex.
# Hybrid model tiers

Codex should select the least expensive model that can safely complete its responsibility:

| Difficulty | Codex responsibility | DeepSeek route |
|---|---|---|
| Low | Routine coordination and final summary | Flash |
| Medium | Planning, contract design, and ordinary review | Flash, with evidence-backed Pro retry when allowed |
| High | Ambiguous architecture, security-sensitive reasoning, or difficult recovery | `deepseek-v4-pro` plus the highest-capability Codex model for decisions/review |

The tiers are guidance, not a second provider credential path. The host Codex model remains responsible for contracts, risk decisions, and integration; the DeepSeek worker never performs those responsibilities.
