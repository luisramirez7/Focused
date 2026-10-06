# Experiment `rei-v1-claude-8543bccd`

- Level: **full** · model: **claude** · variant: **v1** · prompt v1 · generated 2026-10-05 19:49
- Runs: 47 · examples: 47
- Cost: $1.114 total · $0.0237 per email
- Latency: p50 6.3s · p95 9.4s

Scores are per-example means over repetitions, with 95% bootstrap CIs over examples.

| Metric | Score | n |
|---|---|---|
| citations_valid | 100% [100%, 100%] | 41 |
| escalation_reason_correct | 100% [100%, 100%] | 7 |
| facts_present | 100% [100%, 100%] | 23 |
| forbidden_absent | 96% [89%, 100%] | 47 |
| has_outcome | 100% [100%, 100%] | 47 |
| no_forbidden_tool | 100% [100%, 100%] | 14 |
| no_repeated_calls | 100% [100%, 100%] | 47 |
| no_unapproved_booking | 100% [100%, 100%] | 47 |
| numeric_claims_grounded | 100% [100%, 100%] | 14 |
| order_invariants_ok | 100% [100%, 100%] | 47 |
| outcome_correct | 100% [100%, 100%] | 47 |
| pii_absent_in_model_input | 100% [100%, 100%] | 47 |
| pii_absent_in_reply | 100% [100%, 100%] | 47 |
| required_citations_present | 100% [100%, 100%] | 1 |
| tool_args_correct | 100% [100%, 100%] | 13 |
| tool_call_count | 2.3 [1.9, 2.7] | 47 |
| tools_expected_called | 100% [100%, 100%] | 22 |
| trajectory_match | 100% [100%, 100%] | 22 |
| within_budgets | 100% [100%, 100%] | 47 |

## By slice (directional — small n per slice)

| Slice | n | outcome_correct | forbidden_absent | numeric_claims_grounded |
|---|---|---|---|---|
| adversarial | 5 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| confidentiality | 7 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| edge | 9 | 100% [100%, 100%] | 89% [67%, 100%] | 100% [100%, 100%] |
| fair_housing | 5 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| grounding | 7 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| normal | 10 | 100% [100%, 100%] | 90% [70%, 100%] | 100% [100%, 100%] |
| out_of_scope | 4 | 100% [100%, 100%] | 75% [25%, 100%] | 100% [100%, 100%] |
| pii | 4 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| tool_failure | 4 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |

## Outcome confusion matrix, lenient (an acceptable alternative counts as correct)

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 30 | 0 | 0 | 0 | 0 |
| propose_booking | 0 | 3 | 0 | 0 | 0 |
| clarify | 0 | 0 | 7 | 0 | 0 |
| escalate | 0 | 0 | 0 | 7 | 0 |

## Strict confusion matrix (vs the single expected_outcome)

Shows the agent's tendencies (e.g. escalating where a reply was the primary label) even when the alternative was acceptable.

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 25 | 0 | 1 | 1 | 0 |
| propose_booking | 0 | 3 | 0 | 0 | 0 |
| clarify | 0 | 0 | 6 | 0 | 0 |
| escalate | 5 | 0 | 0 | 6 | 0 |

<!-- raw: {"lenient": {"reply": {"reply": 30, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 3, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 7, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 7, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}}, "strict": {"reply": {"reply": 25, "propose_booking": 0, "clarify": 1, "escalate": 1, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 3, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 6, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 5, "propose_booking": 0, "clarify": 0, "escalate": 6, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}}} -->
