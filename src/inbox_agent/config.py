"""Environment loading and model factories.

Every model the project uses is built here so that the A/B comparison, the judge, and the
embeddings are configured in exactly one place.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
REPORTS_DIR = REPO_ROOT / "reports"

load_dotenv(REPO_ROOT / ".env")

AgentModelName = Literal["claude", "glm"]

CLAUDE_AGENT_MODEL = "claude-sonnet-5-5"
DEFAULT_JUDGE_MODEL = "claude-haiku-4-5"


class ConfigError(RuntimeError):
    """Raised when a required environment variable is missing (CLI exit code 3)."""


def require_env(*names: str) -> None:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise ConfigError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
        )


@dataclass(frozen=True)
class Settings:
    agent_model: AgentModelName
    judge_model: str
    langsmith_project: str
    fireworks_llm_model: str
    fireworks_embedding_model: str


@lru_cache(maxsize=1)
def settings() -> Settings:
    agent = os.environ.get("AGENT_MODEL", "glm")
    if agent not in ("claude", "glm"):
        raise ConfigError(f"AGENT_MODEL must be 'claude' or 'glm', got {agent!r}")
    return Settings(
        agent_model=agent,  # type: ignore[arg-type]
        judge_model=os.environ.get("JUDGE_MODEL", DEFAULT_JUDGE_MODEL),
        langsmith_project=os.environ.get("LANGSMITH_PROJECT", "Focused"),
        fireworks_llm_model=os.environ.get(
            "FIREWORKS_LLM_MODEL", "accounts/fireworks/models/glm-5p3"
        ),
        fireworks_embedding_model=os.environ.get(
            "FIREWORKS_EMBEDDING_MODEL", "accounts/fireworks/models/qwen3-embedding-8b"
        ),
    )


def _anthropic_headers() -> dict[str, str]:
    # The key in use is not workspace-scoped, so Anthropic requires this header (research R5).
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    return {"anthropic-workspace-id": workspace} if workspace else {}


def make_agent_model(name: AgentModelName):
    """Build the agent chat model for one arm of the A/B."""
    if name == "claude":
        require_env("ANTHROPIC_API_KEY")
        from langchain_anthropic import ChatAnthropic

        # Sonnet 5.5 rejects forced tool_choice and `temperature`; explicit adaptive thinking lets
        # ToolStrategy structured output work (research R3).
        return ChatAnthropic(
            model=CLAUDE_AGENT_MODEL,
            default_headers=_anthropic_headers(),
            thinking={"type": "adaptive"},
            max_tokens=8000,
        )
    if name == "glm":
        require_env("FIREWORKS_API_KEY")
        from langchain_fireworks import ChatFireworks

        return ChatFireworks(model=settings().fireworks_llm_model, temperature=0, max_tokens=4000)
    raise ConfigError(f"Unknown agent model {name!r}")


def make_judge_model(name: str | None = None):
    """Build the LLM judge (Claude Haiku 4.5 by default)."""
    require_env("ANTHROPIC_API_KEY")
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=name or settings().judge_model,
        default_headers=_anthropic_headers(),
        temperature=0,
        max_tokens=2000,
    )


def make_embeddings():
    require_env("FIREWORKS_API_KEY")
    from langchain_fireworks import FireworksEmbeddings

    return FireworksEmbeddings(model=settings().fireworks_embedding_model)


def exit_on_config_error(err: ConfigError) -> None:
    print(f"Configuration error: {err}", file=sys.stderr)
    raise SystemExit(3)
