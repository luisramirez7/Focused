"""In-process data store over the JSON fixtures (bookings and escalations live in memory)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

from .config import DATA_DIR
from .schemas import Agent, Booking, Contact, Escalation, Listing, ShowingSlot

FIXTURES = DATA_DIR / "fixtures"
DEFAULT_AGENT_ID = "A-0"

_STOPWORDS = {"the", "a", "an", "on", "at", "in", "house", "home", "property", "listing", "of"}


class BookingError(ValueError):
    """Booking rejected by business rules (message is model-facing)."""


def idempotency_key(listing_id: str, slot_id: str, contact_email: str) -> str:
    raw = f"{listing_id}|{slot_id}|{contact_email.lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class Store:
    def __init__(self, fixtures_dir: Path = FIXTURES):
        self._dir = fixtures_dir
        self.reset()

    def reset(self) -> None:
        listings = json.loads((self._dir / "listings.json").read_text())
        people = json.loads((self._dir / "contacts.json").read_text())
        slots = json.loads((self._dir / "slots.json").read_text())
        self.listings: dict[str, Listing] = {d["listing_id"]: Listing(**d) for d in listings}
        self.agents: dict[str, Agent] = {d["agent_id"]: Agent(**d) for d in people["agents"]}
        self.contacts: dict[str, Contact] = {
            d["email"].lower(): Contact(**d) for d in people["contacts"]
        }
        self.slots: dict[str, ShowingSlot] = {d["slot_id"]: ShowingSlot(**d) for d in slots}
        self.bookings: dict[str, Booking] = {}
        self.escalations: list[Escalation] = []

    # --- listings -------------------------------------------------------------------------

    def find_listings(self, query: str, limit: int = 5) -> list[dict]:
        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in _STOPWORDS]
        if not terms:
            return []
        scored = []
        for listing in self.listings.values():
            haystack = f"{listing.address} {listing.description} {listing.listing_id}".lower()
            score = sum(1 for t in terms if t in haystack)
            if score:
                scored.append((score, listing))
        scored.sort(key=lambda x: (-x[0], x[1].listing_id))
        return [
            {
                "listing_id": item.listing_id,
                "address": item.address,
                "status": item.status,
                "price": item.price,
            }
            for _, item in scored[:limit]
        ]

    def get_listing(self, listing_id: str) -> dict | None:
        listing = self.listings.get(listing_id.strip().upper())
        return listing.public_view() if listing else None

    def confidential_notes(self, listing_id: str) -> str:
        """For evaluators only — never exposed through a tool."""
        listing = self.listings.get(listing_id)
        return listing.seller_notes_confidential if listing else ""

    # --- contacts -------------------------------------------------------------------------

    def get_contact(self, email: str) -> dict:
        contact = self.contacts.get(email.strip().lower())
        if not contact:
            return {"known": False, "buyer_agreement": "not_signed", "assigned_agent_id": None}
        return {"known": True, **contact.model_dump()}

    # --- showings -------------------------------------------------------------------------

    def open_slots(self, listing_id: str, on: date | None = None, limit: int = 6) -> list[dict]:
        out = []
        for slot in sorted(self.slots.values(), key=lambda s: s.start):
            if slot.listing_id != listing_id or not slot.available:
                continue
            if on and slot.start.date() != on:
                continue
            out.append({"slot_id": slot.slot_id, "start": slot.start.isoformat()})
            if len(out) >= limit:
                break
        return out

    def book(
        self,
        listing_id: str,
        slot_id: str,
        contact_email: str,
        decided_by: str = "coordinator",
        now: datetime | None = None,
    ) -> Booking:
        key = idempotency_key(listing_id, slot_id, contact_email)
        if key in self.bookings:  # retry / duplicate approval: no second booking
            return self.bookings[key]
        listing = self.listings.get(listing_id)
        if not listing:
            raise BookingError(f"listing {listing_id} not found")
        if listing.status != "active":
            raise BookingError(f"listing {listing_id} is {listing.status}; showings unavailable")
        if self.get_contact(contact_email)["buyer_agreement"] != "signed":
            raise BookingError(
                f"{contact_email} has no signed buyer agreement on file; cannot book a showing"
            )
        slot = self.slots.get(slot_id)
        if not slot or slot.listing_id != listing_id:
            raise BookingError(f"slot {slot_id} does not belong to listing {listing_id}")
        if not slot.available:
            raise BookingError(f"slot {slot_id} is no longer available")
        if now and slot.start <= now:
            raise BookingError(f"slot {slot_id} is in the past")
        slot.available = False
        booking = Booking(
            booking_id=f"B-{len(self.bookings) + 1:04d}",
            idempotency_key=key,
            listing_id=listing_id,
            slot_id=slot_id,
            contact_email=contact_email.lower(),
            decided_by=decided_by,
        )
        self.bookings[key] = booking
        return booking

    # --- escalations ----------------------------------------------------------------------

    def escalate(
        self, reason_category: str, internal_note: str, listing_id: str | None = None
    ) -> Escalation:
        agent_id = DEFAULT_AGENT_ID
        if listing_id and listing_id in self.listings:
            agent_id = self.listings[listing_id].listing_agent_id
        esc = Escalation(
            escalation_id=f"X-{len(self.escalations) + 1:04d}",
            reason_category=reason_category,
            internal_note=internal_note,
            assigned_agent_id=agent_id,
            listing_id=listing_id,
        )
        self.escalations.append(esc)
        return esc


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store
