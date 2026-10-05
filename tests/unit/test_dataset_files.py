import json
from collections import Counter, defaultdict

import pytest

from inbox_agent.config import DATA_DIR
from inbox_agent.faults import FaultPlan
from inbox_agent.schemas import Email

SLICES = {
    "normal",
    "edge",
    "grounding",
    "fair_housing",
    "confidentiality",
    "out_of_scope",
    "adversarial",
    "tool_failure",
    "pii",
}
OUTCOMES = {"reply", "propose_booking", "clarify", "escalate"}
TOOLS = {
    "search_listings",
    "get_listing",
    "get_contact",
    "check_availability",
    "book_showing",
    "escalate_to_agent",
    "search_knowledge_base",
}
REQUIRED_OUT = {
    "expected_outcome",
    "acceptable_outcomes",
    "expected_first_tool",
    "expected_tools",
    "forbidden_tools",
    "expected_tool_args",
    "required_facts",
    "forbidden_content",
    "expected_docs",
    "expected_escalation_reason",
}


def load(name):
    return [json.loads(line) for line in (DATA_DIR / "datasets" / name).read_text().splitlines()]


GOLDEN = load("golden.jsonl")
KB_DOCS = {p.stem for p in (DATA_DIR / "kb").glob("*.md")}
LISTINGS = {d["listing_id"] for d in json.loads((DATA_DIR / "fixtures/listings.json").read_text())}


@pytest.mark.parametrize("row", GOLDEN, ids=[r["id"] for r in GOLDEN])
def test_golden_example_matches_contract(row):
    Email(**row["inputs"]["email"])
    FaultPlan(row["inputs"].get("fault_plan"))
    out = row["outputs"]
    assert REQUIRED_OUT <= set(out)
    assert out["expected_outcome"] in OUTCOMES
    assert out["expected_outcome"] in out["acceptable_outcomes"]
    assert set(out["acceptable_outcomes"]) <= OUTCOMES
    assert set(out["expected_tools"]) <= TOOLS and set(out["forbidden_tools"]) <= TOOLS
    assert not set(out["expected_tools"]) & set(out["forbidden_tools"])
    assert set(out["expected_docs"]) <= KB_DOCS
    for tool, args in out["expected_tool_args"].items():
        assert tool in TOOLS, f"expected_tool_args key {tool!r} must be a tool name"
        assert isinstance(args, dict), f"expected_tool_args[{tool!r}] must be an object of args"
        if "listing_id" in args:
            assert args["listing_id"] in LISTINGS
    assert set(row["metadata"]["slices"]) <= SLICES
    assert row["split"] in ("dev", "heldout")


def test_every_slice_has_five_examples_and_both_splits():
    counts = Counter(s for r in GOLDEN for s in r["metadata"]["slices"])
    assert all(counts[s] >= 5 for s in SLICES), counts
    splits = defaultdict(set)
    for r in GOLDEN:
        splits[r["metadata"]["slices"][0]].add(r["split"])
    assert all(v == {"dev", "heldout"} for v in splits.values()), dict(splits)


def test_ids_unique():
    assert len({r["id"] for r in GOLDEN}) == len(GOLDEN)


def test_retrieval_covers_every_doc():
    rows = load("retrieval.jsonl")
    covered = {d for r in rows for d in r["outputs"]["expected_doc_ids"]}
    assert covered == KB_DOCS
