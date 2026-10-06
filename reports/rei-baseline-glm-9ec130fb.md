# Experiment `rei-baseline-glm-9ec130fb`

- Level: **full** · model: **glm** · variant: **baseline** · prompt v0 · generated 2026-10-05 19:18
- Runs: 195 · examples: 65
- Cost: $1.319 total · $0.0068 per email
- Latency: p50 15.6s · p95 41.4s

Scores are per-example means over repetitions, with 95% bootstrap CIs over examples.

| Metric | Score | n |
|---|---|---|
| citations_valid | 100% [100%, 100%] | 64 |
| escalation_reason_correct | 100% [100%, 100%] | 22 |
| facts_present | 94% [87%, 99%] | 35 |
| forbidden_absent | 98% [96%, 100%] | 65 |
| has_outcome | 100% [100%, 100%] | 65 |
| no_forbidden_tool | 90% [75%, 100%] | 17 |
| no_repeated_calls | 99% [98%, 100%] | 65 |
| no_unapproved_booking | 100% [100%, 100%] | 65 |
| numeric_claims_grounded | 100% [100%, 100%] | 52 |
| order_invariants_ok | 100% [100%, 100%] | 65 |
| outcome_correct | 100% [100%, 100%] | 65 |
| pii_absent_in_model_input | 100% [100%, 100%] | 65 |
| pii_absent_in_reply | 100% [100%, 100%] | 65 |
| required_citations_present | 100% [100%, 100%] | 1 |
| tool_args_correct | 100% [100%, 100%] | 19 |
| tool_call_count | 3.6 [3.4, 3.9] | 65 |
| tools_expected_called | 100% [100%, 100%] | 30 |
| trajectory_match | 100% [100%, 100%] | 30 |
| within_budgets | 99% [98%, 100%] | 65 |

## By slice (directional — small n per slice)

| Slice | n | outcome_correct | forbidden_absent | numeric_claims_grounded |
|---|---|---|---|---|
| adversarial | 7 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| confidentiality | 9 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| edge | 14 | 100% [100%, 100%] | 98% [93%, 100%] | 100% [100%, 100%] |
| fair_housing | 7 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| grounding | 10 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| normal | 13 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| out_of_scope | 6 | 100% [100%, 100%] | 89% [67%, 100%] | 100% [100%, 100%] |
| pii | 5 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| tool_failure | 6 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |

## Outcome confusion matrix (rows = expected, columns = predicted, all runs)

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 103 | 0 | 0 | 0 | 0 |
| propose_booking | 0 | 18 | 0 | 0 | 0 |
| clarify | 0 | 0 | 13 | 0 | 0 |
| escalate | 0 | 0 | 0 | 61 | 0 |

<!-- raw: {"reply": {"reply": 103, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 18, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 13, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 61, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}} -->
