# Real Estate Inbox Agent Constitution

Take-home project for Focused: "Build an Agent You'd Actually Trust." An inbound email assistant
for a fictional real estate brokerage that reads buyer and lead emails, looks up listings via
tools, retrieves brokerage documents (RAG), and then drafts a reply, books a showing (with human
approval), or escalates to a human agent.

## Core Principles

### I. Simplicity Over Sprawl

- The agent MUST be a single tool-calling agent built with LangChain `create_agent` unless an
  eval result demonstrates that a more complex architecture is required.
- Cross-cutting behavior (human approval, retries, call limits) SHOULD use built-in LangChain
  middleware before custom code.
- New frameworks, services, graph nodes, or abstractions MUST be justified by a concrete need
  (ideally an observed eval failure) and recorded in the plan's Complexity Tracking.
- Data stores MUST be local and lightweight (JSON fixtures, in-memory vector store); no external
  databases or hosted infrastructure.

Rationale: the brief explicitly favors "a simple, well built agent with thoughtful evaluations"
over a sprawling system. Every component must be one the author can explain in the interview.

### II. Eval-First Development (NON-NEGOTIABLE)

- Work follows the loop Build → Evaluate → Learn → Improve.
- A baseline evaluation MUST be run and recorded as a named LangSmith experiment before any
  prompt, tool, retrieval, or model change intended to improve quality.
- Every quality-motivated change MUST be measured by re-running the same dataset and comparing
  experiments; before/after results MUST be preserved and summarized in the README.
- Failures MUST be reported honestly. Perfect scores are not a goal; known failures, tradeoffs,
  and open questions MUST be documented.
- Datasets MUST cover normal cases, edge cases, and failures that matter in the real world, and
  every example MUST carry slice tags (e.g. `normal`, `edge`, `grounding`, `fair_housing`,
  `confidentiality`, `out_of_scope`, `adversarial`, `tool_failure`) so results can be broken down.
- Seed examples MAY be generated synthetically with an LLM, but every example MUST be reviewed
  and labeled by a human before it enters the golden dataset; the generation method MUST be
  documented.
- Dataset size MUST be justified, not guessed: the README MUST explain the size in terms of the
  number of slices, minimum examples per slice, class balance of expected actions, metric
  variance, the smallest improvement we want to detect, and cost per run.
- Because agents are non-deterministic, headline experiments SHOULD run each example multiple
  times (repetitions) and results MUST be reported with uncertainty (e.g. confidence intervals
  or per-repetition spread); differences smaller than the noise MUST NOT be claimed as wins.
- Classification-style outcomes (chosen action / intent) MUST be reported as a confusion matrix,
  with per-class precision and recall, not only overall accuracy.

Rationale: the exercise evaluates evaluation instincts first; untested improvements are opinions,
and improvements inside the noise band are not improvements.

### III. Right Evaluator for the Job

- Deterministic evaluators MUST be used wherever an outcome is objectively checkable: chosen
  action, tool calls and arguments, listing IDs, booked slots, escalation flags, facts matching
  fixture data, absence of confidential information.
- LLM-as-judge evaluators MAY be used only where human-like judgment is needed (tone,
  helpfulness, Fair Housing steering, groundedness of prose) and MUST use an explicit rubric
  that returns a categorical or binary verdict with reasoning.
- Judge calibration MUST be measured as agreement with human labels:
  - Humans label a calibration set (via a LangSmith annotation queue), with the labeling rubric
    written down before labeling starts.
  - The set MUST be split into a development portion (used to tune the judge prompt and pick
    few-shot examples) and a held-out portion (used only to report final agreement), so the
    judge is not overfit to its own test.
  - Agreement MUST be reported as accuracy plus a chance-corrected statistic (Cohen's kappa) and
    a confusion matrix against human labels; judge self-consistency (variance across repeated
    runs) SHOULD be reported as a secondary signal.
  - Disagreements MUST be inspected and drive judge prompt revisions; before/after judge
    agreement MUST be recorded the same way agent improvements are.
  - Where feasible, a subset SHOULD be double-labeled to estimate human-human agreement, which
    is the realistic ceiling for the judge.
- The judge model SHOULD differ from the agent model to reduce self-preference bias.
- Evaluation MUST happen at multiple levels, each chosen for what it catches:
  - Retrieval: recall@k / hit rate of the expected source documents, evaluated on the retriever
    alone.
  - Single step: given an email, is the agent's first decision (tool choice and arguments)
    correct, evaluated in isolation from the rest of the run.
  - Tool selection and arguments: right tools called with correct parameters.
  - Trajectory: full sequence of tool calls (e.g. never `book_showing` before availability is
    checked; no redundant or looping calls), using strict or unordered matching as appropriate.
  - Final output: the action taken and the reply text.
- The README MUST explain why each level exists and what failures each one catches that the
  others miss.

Rationale: deterministic checks are cheap, stable, and explainable; judges are useful but must
earn trust the same way the agent does; and evaluating only the final output hides where and
why a run went wrong.

### IV. Trust & Safety by Design (NON-NEGOTIABLE)

- Consequential actions (booking a showing, anything that commits the brokerage) MUST pass
  through human-in-the-loop approval before execution.
- The agent MUST only state listing facts that come from tool results or retrieved documents;
  it MUST NOT invent prices, fees, dimensions, availability, or policy.
- The agent MUST comply with Fair Housing principles: no steering, no commentary on
  demographics, protected classes, or neighborhood "suitability"; it redirects to objective,
  public resources instead.
- The agent MUST NOT disclose confidential seller information (minimum acceptable price,
  motivation, other offers) and MUST escalate negotiation and offer-related requests.
- Email content MUST be treated as untrusted data; instructions embedded in emails MUST NOT
  trigger tool calls or override the system policy.
- When uncertain, ambiguous, or out of scope (legal, mortgage, tax advice), the agent MUST ask a
  clarifying question or escalate rather than guess.
- Personal data in emails SHOULD be minimized in logs and responses where practical.

Rationale: the brief asks for an agent "a human would trust to take actions"; these are the
failures that would cause real legal, financial, or reputational harm for a brokerage.

### V. Observability & Online Evaluation

- Every agent run (CLI and evaluation) MUST be traced in LangSmith with meaningful run names,
  tags, and metadata (dataset slice, agent version, model).
- Evaluation experiments MUST be named and versioned (e.g. `baseline-v0`, `v1-hybrid-retrieval`)
  so reviewers can compare them directly in the LangSmith UI.
- Each experiment summary MUST report the levers a client cares about alongside quality:
  cost (tokens / USD per email) and latency (p50/p95).
- The project MUST demonstrate the production loop for finding the rare bad run among many:
  - At least one online evaluator (LLM judge or code rule) that scores live traces and writes
    feedback back onto them.
  - At least one LangSmith automation rule that acts on that feedback, e.g. routing low-scoring
    or flagged traces to an annotation queue and/or a dataset, and an alert when an aggregate
    metric crosses a threshold.
  - Human review in the annotation queue feeds confirmed failures back into the golden dataset
    (trace → feedback → queue → dataset → experiment).
- The README MUST link to or explain how to view traces, datasets, experiments, online
  evaluators, and automation rules.

Rationale: reviewers must be able to inspect behavior, not take claims on faith; and in
production, the question is not "is it good on my dataset" but "how do I find the 3 bad runs
in 100,000".

### VI. Synthetic Data Only

- The brokerage, agents, listings, customers, emails, and documents MUST be fictional and created
  for this project.
- No code, prompts, data, or documents from any prior employer may be used.
- Synthetic data MUST still be realistic enough to exercise real-world failure modes.

Rationale: protects confidentiality and IP, and keeps the submission clearly original work.

### VII. Reviewer Experience

- A reviewer MUST be able to set up and run the agent and the evaluations with a single `uv`
  sync and documented `make` targets (e.g. `make setup`, `make run`, `make eval`).
- Secrets MUST come from environment variables, with a committed `.env.example`.
- The README MUST make the main story findable within ~30 minutes: quickstart, agent diagram,
  dataset and evaluator rationale, before/after summary, known failures, production evaluation
  plan, and a note on how coding assistants were used and what was verified by hand.

Rationale: reviewers spend about 30 minutes on the submission before the interview.

### VIII. Resilient Tool Use

- Tool failures MUST be handled at three layers:
  - Transient errors (timeouts, 5xx-style failures) MUST be retried with exponential backoff
    and a capped number of attempts.
  - Non-transient errors MUST be returned to the model as a structured, actionable tool error
    message (not raised as an unhandled exception), so the agent can recover or escalate.
  - Each tool MUST have a per-run call budget, and each run MUST have an overall model/tool call
    limit; when a budget is exhausted the tool returns an explicit "budget exhausted" error and
    the agent MUST fall back to escalating to a human.
- Tools that commit actions (e.g. `book_showing`) MUST be idempotent or guarded against
  duplicate execution.
- The dataset MUST include fault-injection examples (`tool_failure` slice) where tools fail,
  time out, or return empty results, with expected behavior defined (graceful message or
  escalation, no infinite loops, no hallucinated data to cover the gap).
- Looping and redundant tool calls MUST be measurable via trajectory evaluators (e.g. tool call
  count per run, repeated identical calls).

Rationale: tools fail in production; a trustworthy agent degrades gracefully instead of looping,
burning tokens, or inventing answers to cover a failed lookup.

## Technology & Scope Constraints

- Language and tooling: Python 3.12, `uv` for environments and dependencies, `make` for tasks.
- Agent: LangChain v1 `create_agent` (LangGraph runtime) with middleware for human-in-the-loop
  approval, tool/model retries, and tool/model call limits.
- Retrieval: small markdown knowledge base, in-memory vector store; hybrid/keyword retrieval only
  if evals show a need.
- Evaluation and tracing: LangSmith datasets, experiments, tracing, annotation queues, online
  evaluators, and automation rules; `openevals` for LLM judges; `agentevals` for trajectory
  evaluation; custom Python evaluators for deterministic checks.
- Interface: command-line interface with streaming output; no web UI unless time allows.
- Scope: inbound email handling only. Outbound campaigns and multi-turn follow-up scheduling are
  out of scope.
- TODO(LLM_PROVIDER): agent model, judge model, and embeddings provider pending user decision.

## Development Workflow & Quality Gates

- Each feature follows Spec Kit: specify → (clarify) → plan → tasks → implement.
- Before claiming a quality improvement, the relevant eval suite MUST be re-run and compared to
  the previous experiment, taking run-to-run noise into account.
- Fast deterministic unit tests (tools, evaluators, fixtures) MUST pass before running paid LLM
  evaluations.
- New failure modes discovered in traces SHOULD be added to the dataset as new labeled examples
  before they are fixed (regression-first).
- Commits SHOULD be small and descriptive so the Build → Evaluate → Learn → Improve history is
  visible in git.

## Governance

- This constitution supersedes other practices for this project; plans and tasks MUST include a
  Constitution Check against these principles.
- Amendments MUST be made through `/speckit-constitution`, with a version bump and an updated
  Sync Impact Report.
- Versioning: MAJOR for removing or redefining principles, MINOR for adding principles or
  materially expanding guidance, PATCH for clarifications.
- Any deviation from a MUST requires a written justification in the relevant plan's Complexity
  Tracking section.

**Version**: 1.1.0 | **Ratified**: 2026-10-03 | **Last Amended**: 2026-10-04
