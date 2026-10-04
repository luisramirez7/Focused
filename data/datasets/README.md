# Datasets

Source of truth lives here in git and is pushed to LangSmith with `make seed-dataset`
(upsert by example id; every change becomes a new LangSmith dataset version tagged with the git
commit).

| File | LangSmith dataset | Purpose |
|---|---|---|
| `golden.jsonl` | `rei-golden` | End-to-end examples with expected outcome, tools, facts, forbidden content, slices, dev/heldout split |
| `retrieval.jsonl` | `rei-retrieval` | Retriever-only queries → expected KB doc ids (level 1) |

## How examples were made

1. **Smoke runs first.** Sample emails in `data/emails/` were run on both models; observations
   (label ambiguity, reason drift, unchecked facts) live in `reports/notes/`.
2. **Drafting.** Examples were drafted with a coding assistant (Claude Code) from the fixtures,
   KB docs, smoke notes, and the spec's edge-case list. `rei draft --slice <slice>` generates
   more candidates with Claude Haiku into `drafts/` (gitignored).
3. **Human review (required).** Every example is reviewed by a person before it counts:
   expected outcome, acceptable alternatives, required facts, forbidden content. Reviewed
   examples have `metadata.reviewed = true`; `metadata.source` records `hand`,
   `synthetic-draft`, or `production-flagged` (promoted from monitoring).

## Labeling conventions

- `acceptable_outcomes` lists every outcome a careful human agent would accept (e.g. an ambiguous
  property reference may be `clarify` or a `reply` that lists both options and asks which).
- `required_facts` use `a|b` for alternatives and are checked case-insensitively in the reply.
- `forbidden_content` includes the referenced listing's confidential phrases; the
  `forbidden_absent` evaluator additionally blocks any dollar amount that exists only in
  confidential seller notes.
- `expected_escalation_reason` is a list of defensible categories, scored separately from the
  outcome.
- Split: every third example of each primary slice is held out (≈70/30), used only for final
  reporting and judge calibration.

## Size rationale (initial — revisited after the baseline)

9 slices × ≥5 examples = ≥45; we have 61. With ~60 examples and 3 repetitions, a pass rate near
85% has a 95% CI of roughly ±9 points, so only overall differences above ~10 points are claimable;
per-slice results (n = 5–11) are directional. Outcome classes are imbalanced (reply 38,
escalate 14, propose_booking 5, clarify 4), so per-class recall for booking/clarify has wide
intervals — reported, not hidden.

## LangSmith pricing note

If GLM-5.3 runs show $0 cost, add a model price entry ($1.40 / $4.40 per MTok) in LangSmith
Settings → Model pricing. (Verified: cost is populated automatically as of 2026-10-04.)
