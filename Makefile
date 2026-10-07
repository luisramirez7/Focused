.PHONY: setup run ui studio test lint seed-dataset pull-dataset eval-baseline eval compare calibrate online-setup

MODEL ?= claude
VARIANT ?= baseline
REPS ?= 1
EMAIL ?= data/emails/oak-st-hoa.json

setup:
	uv sync
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example — fill in your keys.")

run:
	uv run rei run $(EMAIL) --model $(MODEL)

# Streamlit demo: run an email with in-page booking approval, browse eval runs.
ui:
	uv sync --extra ui
	uv run streamlit run streamlit_app.py

# LangGraph Studio: input an Email (e.g. data/emails/*.json), approve bookings in the UI.
# Uses AGENT_MODEL from .env.
studio:
	uv run langgraph dev

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

# Copy edits made in the LangSmith UI back into data/datasets/*.jsonl (run before seed-dataset).
pull-dataset:
	uv run rei pull-dataset

seed-dataset:
	uv run rei setup-langsmith --datasets

# Paid evaluations are gated on the offline unit tests (quality gate).
# Headline run: Claude only, 3 reps (~230 runs, ~$6). GLM-5.3 was evaluated once for the A/B
# (reports/rei-baseline-glm-9ec130fb.md) and is no longer run.
eval-baseline: test
	uv run rei eval --model claude --variant baseline --reps 3

eval: test
	uv run rei eval --model $(MODEL) --variant $(VARIANT) --reps $(REPS)

compare: test
	uv run rei compare $(A) $(B)

calibrate:
	uv run rei calibrate --report

# Create or update the LangSmith online evaluators and rules on the Focused project (idempotent).
# The judge rule keeps its on/off state; ENABLE_JUDGE=1 or ENABLE_JUDGE=0 switches it
# (on needs the ANTHROPIC_API_KEY workspace secret).
online-setup: test
	uv run python -m inbox_agent.evals.online.setup $(if $(filter 1,$(ENABLE_JUDGE)),--enable-judge)$(if $(filter 0,$(ENABLE_JUDGE)),--disable-judge)
