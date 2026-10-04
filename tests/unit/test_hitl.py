from inbox_agent.agent import build_agent, run_email
from tests.fakes import ai, call, email, outcome, scripted

BOOK = dict(listing_id="L-101", slot_id="S-101-0613-1000", contact_email="maya.chen@example.com")


def booking_script(final_kind="propose_booking"):
    extra = (
        {"booking_proposal": {"listing_id": "L-101", "slot_id": "S-101-0613-1000"}}
        if final_kind == "propose_booking"
        else {}
    )
    return scripted(
        ai(call("book_showing", **BOOK)),
        ai(outcome(final_kind, "Your showing request is in.", ["L-101"], **extra)),
    )


def test_booking_pauses_for_approval_and_books_once(store):
    seen = []

    def approve(request):
        seen.append(request)
        return {"type": "approve"}

    agent = build_agent("glm", model=booking_script())
    r = run_email(
        email("Can I see 42 Oak St Saturday 10am?"),
        model_name="glm",
        agent=agent,
        on_interrupt=approve,
    )
    assert r.status == "completed", r.error
    assert seen and seen[0]["name"] == "book_showing"
    assert r.booking and r.booking["slot_id"] == "S-101-0613-1000"
    assert len(store.bookings) == 1


def test_reject_means_no_booking(store):
    agent = build_agent("glm", model=booking_script("reply"))
    r = run_email(
        email("Saturday 10am please"), model_name="glm", agent=agent, approval_policy="reject"
    )
    assert r.status == "completed", r.error
    assert store.bookings == {}
    assert r.booking is None
    assert any(c["name"] == "book_showing" and c["status"] == "error" for c in r.tool_calls)


def test_replayed_approval_does_not_double_book(store):
    for _ in range(2):
        agent = build_agent("glm", model=booking_script())
        run_email(email("Saturday 10am"), model_name="glm", agent=agent, approval_policy="approve")
    assert len(store.bookings) == 1
    assert next(iter(store.bookings.values())).decided_by == "auto-approve"
