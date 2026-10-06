# Experiment `rei-baseline-claude-ac351e89`

- Level: **full** · model: **claude** · variant: **baseline** · prompt v0 · generated 2026-10-05 19:26
- Runs: 195 · examples: 65
- Cost: $0.000 total · $0.0000 per email
- Latency: p50 7.6s · p95 10.7s

Scores are per-example means over repetitions, with 95% bootstrap CIs over examples.

| Metric | Score | n |
|---|---|---|
| citations_valid | 100% [100%, 100%] | 60 |
| escalation_reason_correct | 95% [85%, 100%] | 25 |
| facts_present | 96% [90%, 100%] | 35 |
| forbidden_absent | 94% [88%, 98%] | 65 |
| has_outcome | 100% [100%, 100%] | 65 |
| no_forbidden_tool | 94% [82%, 100%] | 17 |
| no_repeated_calls | 100% [100%, 100%] | 65 |
| no_unapproved_booking | 100% [100%, 100%] | 65 |
| numeric_claims_grounded | 100% [100%, 100%] | 28 |
| order_invariants_ok | 100% [100%, 100%] | 65 |
| outcome_correct | 99% [97%, 100%] | 65 |
| pii_absent_in_model_input | 100% [100%, 100%] | 65 |
| pii_absent_in_reply | 100% [100%, 100%] | 65 |
| required_citations_present | 100% [100%, 100%] | 1 |
| tool_args_correct | 100% [100%, 100%] | 19 |
| tool_call_count | 3.2 [3.0, 3.5] | 65 |
| tools_expected_called | 97% [90%, 100%] | 30 |
| trajectory_match | 97% [90%, 100%] | 30 |
| within_budgets | 100% [100%, 100%] | 65 |

## By slice (directional — small n per slice)

| Slice | n | outcome_correct | forbidden_absent | numeric_claims_grounded |
|---|---|---|---|---|
| adversarial | 7 | 100% [100%, 100%] | 81% [52%, 100%] | 100% [100%, 100%] |
| confidentiality | 9 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| edge | 14 | 100% [100%, 100%] | 98% [93%, 100%] | 100% [100%, 100%] |
| fair_housing | 7 | 90% [71%, 100%] | 95% [86%, 100%] | 100% [100%, 100%] |
| grounding | 10 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| normal | 13 | 100% [100%, 100%] | 97% [92%, 100%] | 100% [100%, 100%] |
| out_of_scope | 6 | 100% [100%, 100%] | 67% [33%, 100%] | 100% [100%, 100%] |
| pii | 5 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| tool_failure | 6 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |

## Outcome confusion matrix (rows = expected, columns = predicted, all runs)

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 82 | 0 | 0 | 2 | 0 |
| propose_booking | 0 | 18 | 0 | 0 | 0 |
| clarify | 0 | 0 | 21 | 0 | 0 |
| escalate | 0 | 0 | 0 | 72 | 0 |

<!-- raw: {"reply": {"reply": 82, "propose_booking": 0, "clarify": 0, "escalate": 2, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 18, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 21, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 72, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}} -->
