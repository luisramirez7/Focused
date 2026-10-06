# Experiment `rei-v1-final-claude-e0c5c33a`

- Level: **full** · model: **claude** · variant: **v1-final** · prompt v1 · generated 2026-10-05 19:56
- Runs: 198 · examples: 66
- Cost: $4.873 total · $0.0246 per email
- Latency: p50 6.5s · p95 10.0s

Scores are per-example means over repetitions, with 95% bootstrap CIs over examples.

| Metric | Score | n |
|---|---|---|
| citations_valid | 100% [100%, 100%] | 58 |
| escalation_reason_correct | 100% [100%, 100%] | 9 |
| facts_present | 98% [94%, 100%] | 36 |
| forbidden_absent | 99% [98%, 100%] | 66 |
| has_outcome | 100% [100%, 100%] | 66 |
| no_forbidden_tool | 100% [100%, 100%] | 18 |
| no_repeated_calls | 100% [100%, 100%] | 66 |
| no_unapproved_booking | 100% [100%, 100%] | 66 |
| numeric_claims_grounded | 100% [100%, 100%] | 22 |
| order_invariants_ok | 100% [100%, 100%] | 66 |
| outcome_correct | 100% [100%, 100%] | 66 |
| pii_absent_in_model_input | 100% [100%, 100%] | 66 |
| pii_absent_in_reply | 100% [100%, 100%] | 66 |
| required_citations_present | 100% [100%, 100%] | 2 |
| tool_args_correct | 100% [100%, 100%] | 19 |
| tool_call_count | 2.3 [2.0, 2.6] | 66 |
| tools_expected_called | 100% [100%, 100%] | 29 |
| trajectory_match | 100% [100%, 100%] | 29 |
| within_budgets | 100% [100%, 100%] | 66 |

## By slice (directional — small n per slice)

| Slice | n | outcome_correct | forbidden_absent | numeric_claims_grounded |
|---|---|---|---|---|
| adversarial | 7 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| confidentiality | 10 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| edge | 14 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| fair_housing | 7 | 100% [100%, 100%] | 95% [86%, 100%] | 100% [100%, 100%] |
| grounding | 10 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| normal | 13 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| out_of_scope | 6 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| pii | 5 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| tool_failure | 6 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |

## Outcome confusion matrix, lenient (an acceptable alternative counts as correct)

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 132 | 0 | 0 | 0 | 0 |
| propose_booking | 0 | 18 | 0 | 0 | 0 |
| clarify | 0 | 0 | 23 | 0 | 0 |
| escalate | 0 | 0 | 0 | 25 | 0 |

## Strict confusion matrix (vs the single expected_outcome)

Shows the agent's tendencies (e.g. escalating where a reply was the primary label) even when the alternative was acceptable.

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 111 | 0 | 5 | 1 | 0 |
| propose_booking | 0 | 18 | 0 | 0 | 0 |
| clarify | 0 | 0 | 18 | 0 | 0 |
| escalate | 21 | 0 | 0 | 24 | 0 |

<!-- raw: {"lenient": {"reply": {"reply": 132, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 18, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 23, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 25, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}}, "strict": {"reply": {"reply": 111, "propose_booking": 0, "clarify": 5, "escalate": 1, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 18, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 18, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 21, "propose_booking": 0, "clarify": 0, "escalate": 24, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}}} -->
