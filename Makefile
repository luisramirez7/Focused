.PHONY: setup run studio test lint seed-dataset eval-baseline eval compare calibrate monitor

MODEL ?= glm
VARIANT ?= baseline
REPS ?= 3
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

seed-dataset:
	uv run rei setup-langsmith --datasets

# Paid evaluations are gated on the offline unit tests (constitution quality gate).
eval-baseline: test
	uv run rei eval --model glm --variant baseline --reps $(REPS)
	uv run rei eval --model claude --variant baseline --reps $(REPS)

eval: test
	uv run rei eval --model $(MODEL) --variant $(VARIANT) --reps $(REPS)

compare: test
	uv run rei compare $(A) $(B)

calibrate:
	uv run rei calibrate --report

monitor:
	uv run rei monitor --since 1h
