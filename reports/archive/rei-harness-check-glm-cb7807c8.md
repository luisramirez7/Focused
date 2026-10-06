# Experiment `rei-harness-check-glm-cb7807c8`

- Level: **full** · model: **glm** · variant: **harness-check** · prompt v0 · generated 2026-10-04 18:50
- Runs: 5 · examples: 5
- Cost: $0.046 total · $0.0091 per email
- Latency: p50 25.5s · p95 35.5s

Scores are per-example means over repetitions, with 95% bootstrap CIs over examples.

| Metric | Score | n |
|---|---|---|
| citations_valid | 100% [100%, 100%] | 5 |
| escalation_reason_correct | 33% [0%, 100%] | 3 |
| facts_present | 100% [100%, 100%] | 3 |
| forbidden_absent | 100% [100%, 100%] | 5 |
| has_outcome | 100% [100%, 100%] | 5 |
| no_repeated_calls | 100% [100%, 100%] | 5 |
| no_unapproved_booking | 100% [100%, 100%] | 5 |
| numeric_claims_grounded | 100% [100%, 100%] | 3 |
| order_invariants_ok | 100% [100%, 100%] | 5 |
| outcome_correct | 100% [100%, 100%] | 5 |
| pii_absent_in_model_input | 100% [100%, 100%] | 5 |
| pii_absent_in_reply | 100% [100%, 100%] | 5 |
| tool_args_correct | 100% [100%, 100%] | 1 |
| tool_call_count | 3.6 [2.4, 4.8] | 5 |
| tools_expected_called | 100% [100%, 100%] | 2 |
| trajectory_match | 100% [100%, 100%] | 2 |
| within_budgets | 100% [100%, 100%] | 5 |

## By slice (directional — small n per slice)

| Slice | n | outcome_correct | forbidden_absent | numeric_claims_grounded |
|---|---|---|---|---|
| normal | 2 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| pii | 5 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |

## Outcome confusion matrix (rows = expected, columns = predicted, all runs)

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 3 | 0 | 0 | 0 | 0 |
| propose_booking | 0 | 1 | 0 | 0 | 0 |
| escalate | 0 | 0 | 0 | 1 | 0 |

<!-- raw: {"reply": {"reply": 3, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 1, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 1, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}} -->
