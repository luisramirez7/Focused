"""Domain and output schemas (data-model.md, contracts/outcome.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ListingStatus = Literal["active", "pending", "sold"]
BuyerAgreement = Literal["signed", "not_signed"]
OutcomeType = Literal["reply", "propose_booking", "clarify", "escalate"]
EscalationReason = Literal[
    "offer",
    "confidential_request",
    "legal_finance",
    "fair_housing",
    "ambiguous",
    "no_buyer_agreement",
    "tool_failure",
    "injection_suspected",
    "other",
]
BookingStatus = Literal["proposed", "approved", "edited", "rejected", "booked"]


class Email(BaseModel):
    email_id: str
    from_address: str
    from_name: str | None = None
    subject: str = ""
    body: str = Field(min_length=1, max_length=8000)
    received_at: datetime

    @field_validator("from_address")
    @classmethod
    def _email_format(cls, v: str) -> str:
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("from_address must be an email address")
        return v.lower()

    def as_prompt(self) -> str:
        """Render the email for the model. The body is wrapped and labelled as untrusted data."""
        sender = f"{self.from_name} <{self.from_address}>" if self.from_name else self.from_address
        return (
            f"New inbound email (received {self.received_at.isoformat()}).\n"
            f"From: {sender}\nSubject: {self.subject}\n"
            '<email_body untrusted="true">\n'
            f"{self.body}\n"
            "</email_body>"
        )


class Listing(BaseModel):
    listing_id: str
    address: str
    status: ListingStatus
    price: int
    hoa_fee_monthly: int | None = None
    beds: int
    baths: float
    sqft: int
    year_built: int
    description: str
    listing_agent_id: str
    seller_notes_confidential: str = ""

    def public_view(self) -> dict:
        """Fields a buyer may see. Confidential seller notes are never included."""
        return self.model_dump(exclude={"seller_notes_confidential"})


class Agent(BaseModel):
    agent_id: str
    name: str
    email: str


class Contact(BaseModel):
    email: str
    name: str
    buyer_agreement: BuyerAgreement
    assigned_agent_id: str | None = None


class ShowingSlot(BaseModel):
    slot_id: str
    listing_id: str
    start: datetime
    available: bool = True


class Booking(BaseModel):
    booking_id: str
    idempotency_key: str
    listing_id: str
    slot_id: str
    contact_email: str
    status: BookingStatus = "booked"
    decided_by: str = "coordinator"


class Escalation(BaseModel):
    escalation_id: str
    reason_category: EscalationReason
    internal_note: str
    assigned_agent_id: str
    listing_id: str | None = None


class EscalationDetail(BaseModel):
    reason_category: EscalationReason
    internal_note: str = Field(description="Note for the human agent explaining why.")


class BookingProposalRef(BaseModel):
    listing_id: str
    slot_id: str


class Outcome(BaseModel):
    """Final result of handling one email. Submit exactly once, as the last step."""

    outcome: OutcomeType = Field(
        description=(
            "reply = answer the sender; propose_booking = a showing was booked via book_showing "
            "after approval; clarify = ask the sender a clarifying question; escalate = hand off "
            "to a human agent (you must also have called escalate_to_agent)."
        )
    )
    message_to_sender: str = Field(
        min_length=1,
        max_length=2000,
        description="Buyer-facing email text. Never include internal notes or confidential data.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Listing ids (e.g. L-101) and knowledge-base doc ids backing the facts stated.",
    )
    escalation: EscalationDetail | None = Field(
        default=None, description="Required if and only if outcome is 'escalate'."
    )
    booking_proposal: BookingProposalRef | None = Field(
        default=None, description="Required if and only if outcome is 'propose_booking'."
    )

    @model_validator(mode="after")
    def _consistency(self) -> Outcome:
        if (self.outcome == "escalate") != (self.escalation is not None):
            raise ValueError("`escalation` is required if and only if outcome == 'escalate'")
        if (self.outcome == "propose_booking") != (self.booking_proposal is not None):
            raise ValueError(
                "`booking_proposal` is required if and only if outcome == 'propose_booking'"
            )
        return self
