"""Agent tools (contracts/tools.md).

Conventions:
- Expected business errors return a string starting with "ERROR:" plus an actionable hint, so the
  model can recover or escalate.
- Transient faults raise TransientToolError; ToolRetryMiddleware retries them.
- No tool ever returns a listing's confidential seller notes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date as Date

from langchain.tools import ToolRuntime, tool

from .faults import FaultPlan, apply_fault
from .retrieval import search as kb_search
from .schemas import EscalationReason
from .store import BookingError, get_store


@dataclass
class RunContext:
    """Per-run context passed to tools via the agent runtime."""

    sender_email: str = ""
    fault_plan: FaultPlan = field(default_factory=FaultPlan)
    decided_by: str = "coordinator"


def _fault(runtime: ToolRuntime[RunContext] | None, tool_name: str) -> str:
    plan = runtime.context.fault_plan if runtime and runtime.context else None
    return apply_fault(tool_name, plan)


def _dump(obj) -> str:
    return json.dumps(obj, default=str)


@tool
def search_listings(query: str, runtime: ToolRuntime[RunContext]) -> str:
    """Search Harborview listings by address fragment or description (e.g. "Oak St",
    "blue craftsman"). Returns up to 5 matches with listing_id, address, status, and price.
    An empty list means no listing matched — never describe a property that was not found."""
    fault = _fault(runtime, "search_listings")
    if fault == "error":
        return "ERROR: listing search is unavailable. Consider escalating with reason tool_failure."
    if fault == "empty":
        return "[]"
    if fault == "malformed":
        return '{"results": [{"listing_id": null, "addr'
    return _dump(get_store().find_listings(query))


@tool
def get_listing(listing_id: str, runtime: ToolRuntime[RunContext]) -> str:
    """Get full public details for one listing by id (e.g. L-101): status, price, monthly HOA fee
    (null means no HOA), beds, baths, sqft, year built, description, listing agent."""
    fault = _fault(runtime, "get_listing")
    if fault == "error":
        return "ERROR: listing service error. Consider escalating with reason tool_failure."
    if fault == "empty":
        return "{}"
    if fault == "malformed":
        return '{"listing_id": "' + listing_id + '", "price": "N/A", "status": '
    listing = get_store().get_listing(listing_id)
    if listing is None:
        return f"ERROR: listing {listing_id} not found. Use search_listings to find the right id."
    return _dump(listing)


@tool
def get_contact(email: str, runtime: ToolRuntime[RunContext]) -> str:
    """Look up a contact by email address. Returns name, buyer_agreement (signed / not_signed),
    and assigned agent. Unknown senders are returned with known=false and not_signed."""
    fault = _fault(runtime, "get_contact")
    if fault == "error":
        return "ERROR: contact directory unavailable. Consider escalating with reason tool_failure."
    if fault == "empty":
        return "{}"
    return _dump(get_store().get_contact(email))


@tool
def check_availability(
    listing_id: str, runtime: ToolRuntime[RunContext], date: str | None = None
) -> str:
    """List open private-showing slots (slot_id, start) for an active listing, optionally on one
    date (YYYY-MM-DD). Returns up to 6 slots."""
    fault = _fault(runtime, "check_availability")
    if fault == "error":
        return "ERROR: scheduling system error. Consider escalating with reason tool_failure."
    if fault == "empty":
        return "[]"
    store = get_store()
    listing = store.get_listing(listing_id)
    if listing is None:
        return f"ERROR: listing {listing_id} not found."
    if listing["status"] != "active":
        return f"ERROR: listing {listing_id} is {listing['status']}; showings are not available."
    on = None
    if date:
        try:
            on = Date.fromisoformat(date)
        except ValueError:
            return "ERROR: date must be YYYY-MM-DD."
    return _dump(store.open_slots(listing_id, on))


@tool
def book_showing(
    listing_id: str, slot_id: str, contact_email: str, runtime: ToolRuntime[RunContext]
) -> str:
    """Book a private showing. Requires an active listing, a signed buyer agreement for the
    contact, and an open slot from check_availability. A Harborview coordinator must approve the
    booking before it executes."""
    fault = _fault(runtime, "book_showing")
    if fault == "error":
        return "ERROR: booking system error. Consider escalating with reason tool_failure."
    decided_by = runtime.context.decided_by if runtime and runtime.context else "coordinator"
    try:
        booking = get_store().book(listing_id, slot_id, contact_email, decided_by=decided_by)
    except BookingError as e:
        return f"ERROR: {e}"
    return _dump(
        {
            "booking_id": booking.booking_id,
            "status": booking.status,
            "listing_id": booking.listing_id,
            "slot_id": booking.slot_id,
        }
    )


@tool
def escalate_to_agent(
    reason_category: EscalationReason,
    internal_note: str,
    runtime: ToolRuntime[RunContext],
    listing_id: str | None = None,
) -> str:
    """Hand this email off to a human agent. Use for offers/negotiation, confidential seller
    requests, legal/mortgage/tax questions, suspected manipulation, tool failures, or anything you
    cannot answer safely. internal_note is for the agent, not the buyer."""
    fault = _fault(runtime, "escalate_to_agent")
    if fault == "error":
        return "ERROR: escalation queue unavailable. Tell the sender a team member will follow up."
    esc = get_store().escalate(reason_category, internal_note, listing_id)
    agent = get_store().agents.get(esc.assigned_agent_id)
    return _dump(
        {
            "escalation_id": esc.escalation_id,
            "assigned_agent": agent.name if agent else esc.assigned_agent_id,
        }
    )


@tool
def search_knowledge_base(query: str, runtime: ToolRuntime[RunContext]) -> str:
    """Search Harborview's policies and FAQs (showing policy, buyer agreements, Fair Housing,
    confidentiality, offers, HOA, disclosures, financing/legal referrals, office info, email
    safety). Returns the top 4 passages with doc_id for citation."""
    fault = _fault(runtime, "search_knowledge_base")
    if fault == "error":
        return "ERROR: knowledge base unavailable. Do not guess policy; consider escalating."
    if fault == "empty":
        return "[]"
    return _dump(kb_search(query, k=4))


TOOLS = [
    search_listings,
    get_listing,
    get_contact,
    check_availability,
    book_showing,
    escalate_to_agent,
    search_knowledge_base,
]

TOOL_BUDGETS = {
    "search_listings": 3,
    "get_listing": 4,
    "get_contact": 2,
    "check_availability": 3,
    "book_showing": 1,
    "escalate_to_agent": 1,
    "search_knowledge_base": 3,
}
