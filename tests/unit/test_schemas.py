import pytest
from pydantic import ValidationError

from inbox_agent.schemas import Email, Outcome


def test_escalate_requires_escalation():
    with pytest.raises(ValidationError):
        Outcome(outcome="escalate", message_to_sender="We'll follow up.")
    Outcome(
        outcome="escalate",
        message_to_sender="ok",
        escalation={"reason_category": "offer", "internal_note": "offer"},
    )


def test_escalation_only_when_escalating():
    with pytest.raises(ValidationError):
        Outcome(
            outcome="reply",
            message_to_sender="hi",
            escalation={"reason_category": "offer", "internal_note": "x"},
        )


def test_propose_booking_requires_proposal():
    with pytest.raises(ValidationError):
        Outcome(outcome="propose_booking", message_to_sender="Booked!")
    Outcome(
        outcome="propose_booking",
        message_to_sender="Booked!",
        booking_proposal={"listing_id": "L-101", "slot_id": "S-101-0613-1000"},
    )


@pytest.mark.parametrize("msg", ["", "x" * 2001])
def test_message_length_bounds(msg):
    with pytest.raises(ValidationError):
        Outcome(outcome="reply", message_to_sender=msg)


def test_email_prompt_marks_body_untrusted():
    e = Email(
        email_id="E-1",
        from_address="A@B.com",
        subject="s",
        body="hello",
        received_at="2026-06-08T09:00:00-07:00",
    )
    assert e.from_address == "a@b.com"
    assert '<email_body untrusted="true">' in e.as_prompt()
