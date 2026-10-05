"""Seed guard + pull logic against a fake LangSmith client (no network)."""

import json
from types import SimpleNamespace

import pytest

from inbox_agent.evals import langsmith_setup as L


def row(i, fact="x"):
    return {
        "inputs": {"q": i},
        "outputs": {"required_facts": [fact]},
        "metadata": {"slices": ["normal"]},
        "id": f"G-{i:03d}",
        "split": "dev",
    }


def remote(r, **changes):
    meta = {**r["metadata"], "example_key": r["id"], "split": r["split"], "dataset_split": ["dev"]}
    ex = SimpleNamespace(
        id=f"uuid-{r['id']}", inputs=r["inputs"], outputs=r["outputs"], metadata=meta
    )
    for k, v in changes.items():
        setattr(ex, k, v)
    return ex


@pytest.fixture
def env(tmp_path, monkeypatch):
    (tmp_path / "datasets").mkdir()
    monkeypatch.setattr(L, "DATA_DIR", tmp_path)
    state = {"remote": []}
    client = SimpleNamespace(
        has_dataset=lambda **k: True,
        list_examples=lambda **k: list(state["remote"]),
        read_dataset=lambda **k: SimpleNamespace(id="ds"),
    )
    monkeypatch.setattr(L, "_client", lambda: client)

    def write(rows):
        (tmp_path / "datasets" / "g.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    return state, write, tmp_path / "datasets" / "g.jsonl"


def test_drift_detects_ui_edits_and_ui_only_examples(env):
    state, write, _ = env
    a, b = row(1), row(2)
    write([a, b])
    state["remote"] = [
        remote(a),
        remote(b, outputs={"required_facts": ["edited"]}),
        SimpleNamespace(id="u9", inputs={}, outputs={}, metadata={}),
    ]
    drift = L.remote_drift("rei-golden", "g.jsonl")
    assert "G-002" in drift and any("only in LangSmith" in d for d in drift)
    assert "G-001" not in drift


def test_seed_refuses_when_ui_edits_exist(env):
    state, write, _ = env
    a = row(1)
    write([a])
    state["remote"] = [remote(a, outputs={"required_facts": ["edited"]})]
    with pytest.raises(SystemExit):
        L.seed_dataset("rei-golden", "g.jsonl", "d")


def test_pull_copies_ui_edits_and_keeps_local_only_rows(env):
    state, write, path = env
    a, b, local_only = row(1), row(2), row(3)
    write([a, b, local_only])
    state["remote"] = [remote(a), remote(b, outputs={"required_facts": ["edited"]})]
    changed = L.pull_dataset("rei-golden", "g.jsonl")
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert changed == ["G-002"]
    assert rows[1]["outputs"]["required_facts"] == ["edited"]
    assert [r["id"] for r in rows] == ["G-001", "G-002", "G-003"]
    assert L.remote_drift("rei-golden", "g.jsonl") == []
