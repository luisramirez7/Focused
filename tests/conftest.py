import json
import os

import pytest

os.environ["LANGSMITH_TRACING"] = "false"  # unit tests never trace


@pytest.fixture
def store():
    from inbox_agent.store import get_store

    s = get_store()
    s.reset()
    yield s
    s.reset()


@pytest.fixture
def fake_kb(monkeypatch):
    """Retrieval backed by a deterministic fake embedding (no network)."""
    from langchain_core.embeddings import DeterministicFakeEmbedding

    from inbox_agent import retrieval

    kb = retrieval.KnowledgeBase(DeterministicFakeEmbedding(size=64))
    monkeypatch.setattr(retrieval, "get_kb", lambda: kb)
    return kb


@pytest.fixture
def confidential_strings():
    from inbox_agent.config import DATA_DIR

    listings = json.loads((DATA_DIR / "fixtures" / "listings.json").read_text())
    return [item["seller_notes_confidential"] for item in listings]
