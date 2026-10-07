# Harborview Inbox Agent

An email assistant for a (fictional) real estate brokerage that answers buyers, books showings
with a human's approval, and escalates what it shouldn't handle — plus the evaluations that show
where it can be trusted and where it can't.

**For reviewers:** [quickstart](#quickstart) · [agent diagram](#how-it-works) ·
[traces and eval runs](#viewing-traces-and-runs) (public links) ·
[before/after](#the-story-in-5-minutes) · [datasets and evaluators](#the-evaluations) ·
[known failures](#known-failures-and-limitations) · screen recording: _link to come_

## The story in 5 minutes

**The agent.** One inbound buyer email in, exactly one outcome out: `reply`, `propose_booking`,
`clarify` or `escalate`. A single LangChain `create_agent` loop with seven tools (listings,
contacts, showing availability, booking, escalation, policy search over 15 brokerage docs) and
built-in middleware for PII redaction, human approval of bookings, retries, per-tool budgets and
a step limit.

**How it's evaluated.** 66 human-reviewed emails across nine slices (normal, edge, grounding,
Fair Housing, seller confidentiality, out-of-scope, prompt injection, tool failure, PII), scored
at five levels from retrieval to final reply. Deterministic checks wherever a right answer exists;
an LLM judge for Fair Housing compliance, calibrated against 50 blind human labels (it catches
explicit steering but missed 3 of 8 subtle cases, so it is a monitor, not the only gate).

## How it works

```mermaid
%%{init: {"flowchart": {"htmlLabels": false, "padding": 16}}}%%
flowchart TD
    E["Buyer email<br/>(untrusted text)"] --> P["PII redaction<br/>card, SSN, bank numbers"]
    P --> M("Claude Sonnet 5.5<br/>create_agent loop")
    M <-->|tool calls| T["Read-only tools<br/>listings, contacts,<br/>availability, policy search"]
    M -->|book_showing| H[["Coordinator approval<br/>approve, edit or reject"]]
    H --> M
    M -->|escalate_to_agent| X["Human agent queue"]
    M --> O["One outcome<br/>reply, propose_booking,<br/>clarify or escalate"]
    G["Guardrails<br/>retries on transient errors<br/>per-tool call budgets<br/>12-call step limit"] -.- M
```

**What the evaluation found and what changed.**

| | Baseline (prompt v0) | Prompt v1 |
|---|---|---|
| Escalated when a reply was the right call | **27%** of runs | **1%** (held-out: 31% → 0%) |
| Tool calls per email | 3.2 | **2.3** |
| Correct outcome | 99% | 100% |
| Trust-gate failures (lookup on a contract-terms request, G-037 held-out) | 3 of 3 runs | 0 of 3 runs |
| Invented numbers · PII leaks · unapproved bookings | 0 · 0 · 0 | 0 · 0 · 0 |
| Cost per email · latency p50 / p95 | $0.025 · 7.4 s / 11.0 s | $0.025 · 6.5 s / 10.0 s |

The baseline's main failure wasn't in the model: my v0 prompt told the agent to escalate every
policy question, while the labeled policy says to close them directly and escalate only when a
human must act. Over-escalation was invisible in the lenient metrics (99% "correct outcome",
because escalating was *allowed*) and obvious in the strict confusion matrix. Prompt v1 fixed it
(−27 points, 95% CI −40 to −14, and the drop held on the held-out split) without moving any
other metric beyond noise. 3 runs per email, both sides re-graded with the same labels; paired
changes use the 65 emails both runs share (G-066 was added before the v1 run).

**Three failures worth reading** (traces linked in [Viewing traces](#viewing-traces-and-runs)):

1. **Every check passed, the run was still wrong.** In LangGraph Studio the agent received no
   email, invented a request from its own tool-description examples ("the blue craftsman on Oak
   St") and escalated it for real. All checks compared output to tool results; none compared it to
   the input. Now regression examples G-062/G-063.
2. **The phrase checks failed on correct refusals.** "I can't say whether an offer would be
   *accepted*" and "Nothing *is booked* for you" tripped `forbidden_content` in 6 of 6 phrase
   failures. Fixed with a negation-aware check (numbers stay strict), logged as an evaluator
   change, and both runs re-graded with it.
3. **The one trust-gate failure was on a held-out example.** The agent looked up a pending
   listing before refusing to share its contract terms. I couldn't tune on it, so I added a dev
   example of the same class (G-066) first, then fixed the prompt, then checked G-037 once.

Full write-ups: [baseline analysis](reports/baseline-analysis.md) ·
[before/after](reports/before-after.md) · [judge calibration](reports/calibration.md) ·
[dataset changelog](data/datasets/CHANGELOG.md).

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and API keys for Anthropic (Claude) and Fireworks
(embeddings), plus LangSmith for tracing and evals.

```bash
make setup                                   # install, create .env from .env.example
make test                                    # offline unit tests, no API calls
make run EMAIL=data/emails/oak-st-hoa.json   # one email, streamed, with the approval prompt
make ui                                      # Streamlit demo: run emails, approve bookings, browse evals
```

Other useful commands:

```bash
uv run rei samples                           # list the sample emails
uv run rei run showing-saturday              # a booking: approve, edit or reject it
uv run rei run injected-signature            # a prompt-injection attempt
uv run rei run oak-st-hoa --fault '{"get_listing":["timeout","timeout","timeout"]}'
uv run rei eval --split dev                  # an experiment (budget-capped; 1 rep by default)
uv run rei compare <before.jsonl> <after.jsonl>
```

- **Output schema.** The final answer is a validated `Outcome` (LangChain `ToolStrategy`), the
  same mechanism for every model so the model comparison stays fair.
- **Retrieval.** Two kinds on purpose. Policy questions use semantic search: each section of
  the 15 policy docs is a chunk, embedded with Qwen3-Embedding-8B in an in-memory vector store,
  top-4 similarity (recall@4 100% on 26 queries, which also means that test set is too easy).
  Listings use exact keyword lookup on address and description: an embedding would happily rank
  "24 Oak Ave" next to "42 Oak St", and a showing at the wrong house is a trust failure. The model
  turns fuzzy descriptions into search terms, and ambiguous matches lead to `clarify`.
- **Grounding.** Tools never return the seller's confidential notes; a leak can only come from
  hallucination or manipulation, which is what the evals probe.
- **Data.** Harborview Realty is fictional: 12 listings, 10 contacts, showing slots and 15 policy
  docs written for this project (`data/`). Nothing comes from a real brokerage or employer.

## The evaluations

**Dataset** (`data/datasets/golden.jsonl`, LangSmith dataset `rei-golden`). 66 emails, 47 dev /
19 held-out, each labeled with the expected outcome and acceptable alternatives, tools and key
arguments, required facts, forbidden content, source docs, the simulated coordinator's decision
and, for resilience tests, injected tool faults. Every example was reviewed by me; 13 hand-edited,
28 mechanical fixes from a dataset linter, 19 judgment calls decided on a review page. Size:
nine slices × at least five examples; with three repetitions an 85% pass rate carries about a ±9
point interval, so only differences of about 10 points overall are claimable and per-slice
numbers are directional.

**Five levels, each catching something the others miss.**

| Level | What runs | Catches |
|---|---|---|
| Retrieval | The retriever alone (26 queries) | Wrong or missing policy docs (recall@4: 100%) |
| First step | The agent stopped after one decision | A wrong opening move, isolated from recovery |
| Tool selection and arguments | Full run | Wrong listing, missing contact check, forbidden actions |
| Trajectory | Full run, call order | Booking before checks, loops, budget hits |
| Outcome and reply | Final answer | Wrong decision, missing facts, invented numbers, leaks, PII |

**Deterministic first, judge second.** Twenty deterministic metrics cover everything with a right
answer, including `numeric_claims_grounded` (every price, fee, square footage and bed/bath count
in a reply must appear in that run's tool outputs). One LLM judge (Claude Haiku 4.5) scores the
judgment call that phrase lists can't: Fair Housing steering.

**Judge calibration.** 50 replies labeled blind in a LangSmith annotation queue against a
written rubric (`data/rubrics/fair_housing_ok.md`), then compared with the judge, in two rounds:

| | Replies | Agreement | Cohen's kappa |
|---|---|---|---|
| Round 1: real agent replies + explicit seeded steering | 30 | 100% | 1.00 |
| Round 2: borderline (8 agent replies to bait emails, 12 hand-written) | 20 | 85% | 0.67 |
| All, held-out split | 25 | 92% | 0.80 |

Round 1's perfect score only showed the judge isn't broken, so round 2 went looking for its
limits. Every disagreement is the dangerous kind: the judge **passed 3 replies I failed**, and
never flagged one I passed. All three state neighborhood facts in answer to a protected-class
question (flat sidewalks for a wheelchair user, a synagogue's walking distance for a buyer who
keeps Shabbat, "busier in the evenings" for a "young couple vs retirees" question). One is a judge
error under the current rubric; two are gaps in the rubric. The agent itself passed all 8 bait
emails. I stopped there rather than revise the judge: the held-out disagreements have been seen,
so a revised judge would need a fresh labeled batch to prove anything. Details:
[reports/calibration.md](reports/calibration.md).

**Honest numbers.** Repetitions are averaged per example before bootstrapping confidence
intervals over examples; before/after uses paired intervals and labels differences inside the
noise as such. Labels changed after seeing results are logged in the changelog, and both sides of
every comparison are re-graded against the same label version (`rei compare`).

## Model comparison

Both models were run once on the full baseline (65 emails × 3 runs; G-066 was added later, so
neither baseline includes it).

| | Claude Sonnet 5.5 | GLM-5.3 (Fireworks) |
|---|---|---|
| Correct outcome · facts present | 99% · 96% | 100% · 94% |
| Cost per email | $0.025 | $0.007 |
| Latency p50 / p95 | 7.4 s / 11.0 s | 15.6 s / 41.4 s |

Quality was within noise; GLM is about 3.5× cheaper but its tail reached 70 s. I kept Claude for
latency and dropped GLM from further runs to keep the evaluation budget small.

## Viewing traces and runs

Public LangSmith links (no account needed):

| What | Link |
|---|---|
| Dataset `rei-golden`, with every experiment run on it | [dataset and experiments](https://smith.langchain.com/public/36968e9f-fdb6-4142-acd8-38aea1da705d/d) |
| Before/after, side by side (baseline v0 vs final v1, 3 reps) | [comparison view](https://smith.langchain.com/public/36968e9f-fdb6-4142-acd8-38aea1da705d/d/compare?selectedSessions=c49d9c03-77f0-4d95-936a-ffd079cbefaf%2C63a240d3-6444-42d2-a854-cd88ba1effb4) |
| Failure 1: no email in, invented request out (Studio) | [trace](https://smith.langchain.com/public/e081fe65-27ad-4caf-9d32-db860d6f920b/r) |
| Failure 2: a correct refusal that the old phrase check failed | [trace](https://smith.langchain.com/public/f1eae03e-e0be-47b2-afe8-3f098a137336/r) |
| Failure 3: G-037 baseline, looks up the pending listing before refusing | [trace](https://smith.langchain.com/public/d3cd3328-6ee5-439c-b5a5-a2507e3ae369/r) |
| Failure 3 fixed: G-037 on prompt v1, policy search only | [trace](https://smith.langchain.com/public/c7a68a0c-65e2-41dc-b2fd-8213f2d90a3d/r) |

The experiments that count are `rei-baseline-claude-57179ee6` (v0), `rei-v1-claude-8543bccd`
(v1 on dev), `rei-v1-final-claude-e0c5c33a` (v1, all 66) and `rei-baseline-glm-9ec130fb`; the
`rei-harness-check-*` runs were smoke tests of the harness. Experiment scores in LangSmith are
as graded at run time; the numbers in this README come from re-grading both sides with the
final labels and evaluators (`rei compare`), so a few cells differ.

- **Reports in the repo:** `reports/*.md` (one per experiment), raw per-run results in
  `reports/raw/*.jsonl`.
- **LangSmith:** project `Focused` (tag `rei`), dataset `rei-golden`, experiments
  `rei-baseline-claude-*` (prompt v0), `rei-v1-*` (prompt v1), `rei-baseline-glm-*`; annotation
  queues `rei-judge-calibration` and `rei-online-review`. Online scores are feedback on the
  traces in `Focused` (feedback panel, runs-table columns, Monitor tab).

## Known failures and limitations

- **Phrase checks are brittle by nature.** Even negation-aware, they can miss a paraphrased leak
  or excuse an assertion inside an "if…" clause. The judge covers Fair Housing; other
  confidentiality wording still relies on phrases plus the strict number check.
- **Small per-slice samples.** 5–14 examples per slice; per-slice results are directional.
- **Class imbalance.** 39 reply, 14 escalate, 6 booking, 6 clarify labels; recall for booking
  and clarify has wide intervals.
- **The Fair Housing judge under-flags subtle steering.** Kappa 0.67 on borderline replies,
  with all 3 misses being missed steering (neighborhood facts tied to a protected-class question).
  Single labeler, so there is no human–human ceiling; the borderline replies were hand-written by
  the same model family that wrote the judge prompt. One judge dimension only: helpfulness and
  groundedness of prose are not judged, and tone is not evaluated at all.
- **Single-email scope.** No threads, outbound follow-ups, or real email/MLS/calendar
  integrations.
- **Online scoring is partly live** (below): four safety checks on every trace and the Fair
  Housing judge on every finished reply; the other cheap checks and the alert are not built, and
  the "production" project also holds smoke and demo runs.
- **Trace budget.** The first baseline exhausted the workspace's monthly trace limit because
  every evaluator call was traced; evaluator tracing is now off and every eval run is
  budget-capped.

## Evaluating it in production

What runs today is marked **live**; the rest is the plan. Setup is code in
`src/inbox_agent/evals/online/` (`make online-setup`), and every check scores the raw trace, so
CLI, Streamlit and Studio runs are all covered.

1. **Trace everything** (**live**) with metadata for prompt version, model and email category;
   PII is anonymized before traces leave the process.
2. **Cheap checks on every run** (**live** for four): a LangSmith code evaluator,
   `rei-safety-checks`, scores 100% of `rei-inbox-agent` traces for `has_outcome`,
   `no_unapproved_booking`, `no_repeated_calls` and `citations_valid`, with the same logic as the
   offline checks. One adaptation: an approved booking is two traces (paused, then resumed with the
   coordinator's decision), so the paused one is not failed for having no outcome and the resumed
   one is checked against the recorded decision. Not yet online: invented numbers, confidential
   amounts and PII in the reply, which need tool outputs or listing data inside the evaluator.
3. **Judging** (**live**): the Fair Housing judge (`rei-fair-housing-judge`, the calibrated
   rubric on Haiku 4.5, capped at $1/week) scores every trace that ends in a reply, writing
   `fair_housing_ok` plus its `reasoning`. It runs inside LangSmith with a workspace secret. At real
   volume it would sample ~5–10% of traffic plus 100% of runs a cheap check flagged or whose
   email touches a protected class. Because it misses subtle neighborhood characterization, it
   routes runs to human review rather than acting as the only gate; next steps are a rubric rule
   for neighborhood facts, a fresh labeled batch to verify it, and a second labeler.
4. **Route** (**live**) **and alert** (plan): an automation rule adds any run that fails a safety
   check or the judge to the `rei-online-review` annotation queue; an alert should fire when the
   average safety score drops over a 15-minute window.
5. **Close the loop:** a reviewer confirms each flagged run; confirmed failures become labeled
   examples in the golden set (regression-first), and the next prompt or model change must beat
   the current version on the same dataset version before release.
6. **Watch the levers a brokerage cares about:** escalation rate (human workload), cost per email
   and p95 latency, alongside quality.

## How coding assistants were used

Claude Code (Opus 5.5) wrote most of the code, tests, fixtures and the first draft of the
dataset, ran the experiments and drafted the analysis, using spec-kit (constitution → spec → plan
→ tasks, kept local rather than in this repo) to keep the scope explicit. What I did and checked myself: chose the domain and the
policies, reviewed and corrected every dataset label (including hard-fail rules the assistant
hadn't proposed), approved every post-baseline label change, made the scope cuts, labeled the
judge calibration set blind, and read the failing traces behind each conclusion. Several
evaluator bugs were found during that review rather than by the assistant.

## Repository layout

```text
src/inbox_agent/        agent, tools, middleware wiring, CLI (rei)
src/inbox_agent/evals/  evaluators, experiments, rescoring, calibration, dataset lint and sync
  online/               LangSmith online evaluators and rules (safety checks, judge, routing)
data/                   fixtures, policy docs, sample emails, datasets, rubrics, calibration set
reports/                analyses, final experiment reports, raw results (superseded runs in archive/)
tests/                  offline unit and integration tests
```
