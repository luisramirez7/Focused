"""LangSmith tracing configuration: tags, metadata, and PII-safe client."""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_core.runnables import RunnableConfig

from . import __version__
from .prompts import PROMPT_VERSION


@lru_cache(maxsize=1)
def langsmith_client():
    """Shared LangSmith client that anonymizes PII before traces leave the process."""
    from langsmith import Client

    from .pii import trace_anonymizer

    return Client(anonymizer=trace_anonymizer())


def tracing_enabled() -> bool:
    return os.environ.get("LANGSMITH_TRACING", "").lower() == "true"


def run_config(
    model: str,
    variant: str = "dev",
    extra_tags: list[str] | None = None,
    thread_id: str | None = None,
) -> RunnableConfig:
    config: RunnableConfig = {
        "run_name": "rei-inbox-agent",
        "tags": ["rei", model, variant, *(extra_tags or [])],
        "metadata": {
            "model": model,
            "variant": variant,
            "prompt_version": PROMPT_VERSION,
            "agent_version": __version__,
        },
        "recursion_limit": 250,  # backstop only; every middleware hook is a graph step. The real
        # step limit is ModelCallLimitMiddleware(run_limit=12).
    }
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}
    return config


def tracing_scope():
    """Context manager that routes all auto-traced runs through the anonymizing client."""
    import langsmith

    return langsmith.tracing_context(client=langsmith_client(), enabled=tracing_enabled())
