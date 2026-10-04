from langchain_core.messages import AIMessage

from inbox_agent.agent import build_agent, run_email
from tests.fakes import ai, call, email, outcome, scripted


def run(model, faults=None):
    return run_email(
        email(), model_name="glm", agent=build_agent("glm", model=model), fault_plan=faults
    )


def test_transient_timeout_is_retried(store):
    model = scripted(ai(call("get_listing", listing_id="L-101")), ai(outcome(citations=["L-101"])))
    r = run(model, {"get_listing": ["timeout"]})
    assert r.status == "completed"
    assert '"hoa_fee_monthly": 285' in r.tool_outputs[0]


def test_persistent_timeout_surfaces_error_to_model(store):
    model = scripted(ai(call("get_listing", listing_id="L-101")), ai(outcome()))
    r = run(model, {"get_listing": ["timeout"] * 3})
    assert r.tool_outputs[0].startswith("ERROR: tool temporarily unavailable after retries")


def test_tool_budget_blocks_extra_calls(store):
    calls = [ai(call("get_contact", email="maya.chen@example.com")) for _ in range(3)]
    r = run(scripted(*calls, ai(outcome())))
    statuses = [c["status"] for c in r.tool_calls if c["name"] == "get_contact"]
    assert statuses[:2] == ["success", "success"] and statuses[2] == "error"


def test_looping_model_hits_step_limit(store, fake_kb):
    loop = [ai(call("search_knowledge_base", query=f"q{i}")) for i in range(20)]
    r = run(scripted(*loop, AIMessage(content="never reached")))
    assert r.status in ("step_limit", "no_outcome")
    assert r.outcome is None
    assert sum(1 for c in r.tool_calls if c["name"] == "search_knowledge_base") <= 12
