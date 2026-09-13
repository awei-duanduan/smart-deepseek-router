# Host-backed escalation

Flash always runs first. Pro runs at most once, on the current candidate state, only when all conditions hold:

- The contract explicitly sets `allow_pro: true`.
- Optional preflight checks passed without changing the repository.
- The Flash SDK result has `finish_reason == "completed"`.
- HEAD/index are unchanged, and every ordinary changed file is inside scope.
- Post-worker acceptance verification failed; every failed check is a normally exited process with a positive exit code and the verifier's explicit `implementation_failure_pattern` matches.
- No captured failed-check output matches the router's common infrastructure-error indicators.

Pro receives the original contract and redacted host failure output, not a claim that Flash succeeded. The same host checks then run again. Another failure ends the route; there is no retry loop, alternate model search, or automatic dependency installation.

No escalation for SDK import/startup/protocol errors, missing key/runtime, unavailable Pro capability, worker `error`/`max-tokens`/unknown finish status, timeout, preflight failure, an empty candidate, scope/size violations, Git mutations, changed verifiers, or recognized infrastructure/permission errors. All failures preserve available changes for Codex inspection.

Output patterns cannot perfectly classify arbitrary test systems. Use known acceptance commands and specific assertion/test-failure markers, never generic `Error` or `.*`. Disable `allow_pro` if evidence is ambiguous. A test that passes after a worker rewrites the test is not independent verification; protect trusted verifier files outside scope. Process output stores only the final 64 KiB; missing evidence means no escalation.

Each attempt defaults to an 8,192-token model output cap, 24 provider requests, a configurable wall limit, and one host-controlled retry maximum. The loopback proxy forces the assigned model and applies the request/token caps. These bounds do not predict total billing because context, tool results, and provider behavior can add usage. No price claims are encoded.
