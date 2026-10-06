from langgraph.types import Command

from inbox_agent.agent import default_checkpointer
from inbox_agent.studio import build_studio_graph
from tests.fakes import email
from tests.unit.test_hitl import booking_script


def test_studio_graph_takes_an_email_and_resumes_approval(store):
    graph = build_studio_graph("glm", model=booking_script())
    graph.checkpointer = default_checkpointer()  # Studio's server supplies this in practice
    config = {"configurable": {"thread_id": "studio-t"}}
    msg = email("Can I see 42 Oak St Saturday 10am?")

    first = graph.invoke({"email": msg.model_dump(mode="json")}, config)
    assert first["__interrupt__"][0].value["action_requests"][0]["name"] == "book_showing"
    assert first["messages"][0].content == msg.as_prompt()

    final = graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config)
    assert final["structured_response"].outcome == "propose_booking"
    assert len(store.bookings) == 1


def test_studio_agent_has_no_own_checkpointer():
    graph = build_studio_graph("glm", model=booking_script())
    assert graph.checkpointer is None
    assert dict(graph.get_subgraphs())["agent"].checkpointer is None


def test_context_from_json_builds_a_fault_plan():
    from inbox_agent.faults import FaultPlan
    from inbox_agent.tools import RunContext

    ctx = RunContext(**{"fault_plan": {"search_listings": ["timeout"]}})
    assert isinstance(ctx.fault_plan, FaultPlan)
    assert ctx.fault_plan.next("search_listings") == "timeout"


def test_agent_refuses_to_start_without_an_email():
    import pytest

    from inbox_agent.agent import MissingEmailError, build_agent

    agent = build_agent("glm", model=booking_script())
    with pytest.raises(MissingEmailError):
        agent.invoke({"messages": []}, {"configurable": {"thread_id": "empty"}})


def test_state_edit_that_skips_ingest_hits_the_guard(store):
    """Replays trace 01a10de9: a Studio state edit applied as ingest_email skipped that step."""
    import pytest

    from inbox_agent.agent import MissingEmailError

    graph = build_studio_graph("glm", model=booking_script())
    graph.checkpointer = default_checkpointer()
    config = {"configurable": {"thread_id": "edited"}}
    graph.update_state(config, {"email": email().model_dump(mode="json")}, as_node="ingest_email")
    with pytest.raises(MissingEmailError):
        graph.invoke(None, config)
    assert store.bookings == {} and store.escalations == []


def test_to_email_accepts_plain_text_with_headers():
    from inbox_agent.studio import STUDIO_SENDER, to_email

    e = to_email("From: Keiko Tanaka <keiko.tanaka@example.com>\nSubject: Blair St\n\nHi there!")
    assert (e.from_address, e.from_name, e.subject, e.body) == (
        "keiko.tanaka@example.com",
        "Keiko Tanaka",
        "Blair St",
        "Hi there!",
    )
    assert to_email("Just a body").from_address == STUDIO_SENDER


def test_to_email_accepts_json_strings_and_rejects_missing_input():
    import json

    import pytest

    from inbox_agent.studio import to_email

    payload = email().model_dump(mode="json")
    assert to_email(json.dumps(payload)).email_id == "E-T"
    assert to_email(json.dumps({"email": payload})).email_id == "E-T"
    with pytest.raises(ValueError, match='"email" key'):
        to_email(None)
