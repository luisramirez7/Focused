from inbox_agent.agent import build_agent, run_email
from tests.fakes import ai, call, email, outcome, scripted


def test_lookup_then_outcome(store):
    model = scripted(
        ai(call("get_listing", listing_id="L-101")),
        ai(outcome(message="The HOA fee for 42 Oak St is $285/month.", citations=["L-101"])),
    )
    result = run_email(email(), model_name="glm", agent=build_agent("glm", model=model))
    assert result.status == "completed", result.error
    assert result.outcome["outcome"] == "reply"
    assert [c["name"] for c in result.tool_calls] == ["get_listing", "Outcome"]
    assert "L-101" in result.listing_ids_seen
    assert any("285" in o for o in result.tool_outputs)
