# US1 smoke run — observations (not fixes)

Prompt v0, both models, 2026-10-04. Raw transcripts: [us1-smoke-raw.md](us1-smoke-raw.md). Traces: LangSmith project `Focused`, tag `smoke`.

| Email | GLM-5.3 | Claude Sonnet 5.5 | Notes |
|---|---|---|---|
| oak-st-hoa | reply, HOA $285 correct, cites L-101 + hoa-basics | same | Claude (CLI run) told Maya she needs a buyer agreement although she has one — never called `get_contact` |
| pending-listing | reply, says pending | reply, says pending | both checked contact unnecessarily |
| three-questions | reply, all 3 answered | reply, all 3 answered | GLM called `check_availability` without being asked |
| unknown-fact | reply, says it doesn't know electricity bill; points to school district | reply | GLM cited `fair-housing-guidance` for a school-bus question (reasonable redirect, odd citation) |
| blue-house-on-oak | **reply** listing both Oak homes + "which one?" | **clarify** | Both handle the ambiguity safely; the *label* differs |

## Candidate dataset/eval implications
- **Label ambiguity**: "present both options and ask which" is a reply-with-question. Decide whether `acceptable_outcomes` for ambiguous emails is `[clarify]` or `[clarify, reply]` — and require the message to ask which property (a `required_facts`-style check) rather than relying only on the label.
- **Unnecessary tool calls** (contact lookups for pure questions, availability checks nobody asked for) → trajectory metric `tool_call_count` should show this; GLM is ~2–3× slower per email (15–24 s vs 6–7 s).
- **Stated-but-unchecked facts** about the sender (buyer agreement status) → a grounding failure that `numeric_claims_grounded` won't catch; candidate for the Haiku `grounded` judge and a dedicated example.
