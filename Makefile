.PHONY: setup run studio test lint seed-dataset pull-dataset eval-baseline eval compare calibrate monitor

MODEL ?= claude
VARIANT ?= baseline
REPS ?= 1
EMAIL ?= data/emails/oak-st-hoa.json

setup:
	uv sync
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example — fill in your keys.")
	uv run rei setup-langsmith --dry-run

run:
	uv run rei run $(EMAIL) --model $(MODEL)

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

# Paid evaluations are gated on the offline unit tests (constitution quality gate).
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

monitor:
	uv run rei monitor --since 1h
