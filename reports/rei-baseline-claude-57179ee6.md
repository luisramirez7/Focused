# Experiment `rei-baseline-claude-57179ee6`

- Level: **full** · model: **claude** · variant: **baseline** · prompt v0 · generated 2026-10-05 19:35
- Runs: 195 · examples: 65
- Cost: $4.784 total · $0.0245 per email
- Latency: p50 7.4s · p95 11.0s

Scores are per-example means over repetitions, with 95% bootstrap CIs over examples.

| Metric | Score | n |
|---|---|---|
| citations_valid | 100% [100%, 100%] | 60 |
| escalation_reason_correct | 95% [85%, 100%] | 25 |
| facts_present | 96% [90%, 100%] | 35 |
| forbidden_absent | 96% [91%, 99%] | 65 |
| has_outcome | 100% [100%, 100%] | 65 |
| no_forbidden_tool | 94% [82%, 100%] | 17 |
| no_repeated_calls | 100% [100%, 100%] | 65 |
| no_unapproved_booking | 100% [100%, 100%] | 65 |
| numeric_claims_grounded | 100% [100%, 100%] | 30 |
| order_invariants_ok | 99% [98%, 100%] | 65 |
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
| edge | 14 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| fair_housing | 7 | 90% [71%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| grounding | 10 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| normal | 13 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| out_of_scope | 6 | 100% [100%, 100%] | 78% [56%, 100%] | 100% [100%, 100%] |
| pii | 5 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |
| tool_failure | 6 | 100% [100%, 100%] | 100% [100%, 100%] | 100% [100%, 100%] |

## Outcome confusion matrix, lenient (an acceptable alternative counts as correct)

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 85 | 0 | 0 | 2 | 0 |
| propose_booking | 0 | 18 | 0 | 0 | 0 |
| clarify | 0 | 0 | 19 | 0 | 0 |
| escalate | 0 | 0 | 0 | 71 | 0 |

## Strict confusion matrix (vs the single expected_outcome)

Shows the agent's tendencies (e.g. escalating where a reply was the primary label) even when the alternative was acceptable.

| expected \ predicted | reply | propose_booking | clarify | escalate | no_outcome |
|---|---|---|---|---|---|
| reply | 84 | 0 | 1 | 32 | 0 |
| propose_booking | 0 | 18 | 0 | 0 | 0 |
| clarify | 0 | 0 | 18 | 0 | 0 |
| escalate | 1 | 0 | 0 | 41 | 0 |

<!-- raw: {"lenient": {"reply": {"reply": 85, "propose_booking": 0, "clarify": 0, "escalate": 2, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 18, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 19, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 71, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}}, "strict": {"reply": {"reply": 84, "propose_booking": 0, "clarify": 1, "escalate": 32, "no_outcome": 0}, "propose_booking": {"reply": 0, "propose_booking": 18, "clarify": 0, "escalate": 0, "no_outcome": 0}, "clarify": {"reply": 0, "propose_booking": 0, "clarify": 18, "escalate": 0, "no_outcome": 0}, "escalate": {"reply": 1, "propose_booking": 0, "clarify": 0, "escalate": 41, "no_outcome": 0}, "no_outcome": {"reply": 0, "propose_booking": 0, "clarify": 0, "escalate": 0, "no_outcome": 0}}} -->
