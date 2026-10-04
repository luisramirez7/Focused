import pytest

from inbox_agent.store import BookingError


def test_get_listing_never_exposes_confidential_notes(store):
    for lid in store.listings:
        assert "seller_notes_confidential" not in store.get_listing(lid)


def test_unknown_sender_is_not_signed(store):
    c = store.get_contact("stranger@example.org")
    assert c == {"known": False, "buyer_agreement": "not_signed", "assigned_agent_id": None}


def test_contact_lookup_is_case_insensitive(store):
    assert store.get_contact("Maya.Chen@Example.com")["buyer_agreement"] == "signed"


def test_booking_is_idempotent(store):
    b1 = store.book("L-101", "S-101-0613-1000", "maya.chen@example.com")
    b2 = store.book("L-101", "S-101-0613-1000", "MAYA.CHEN@example.com")
    assert b1.booking_id == b2.booking_id
    assert len(store.bookings) == 1
    assert store.slots["S-101-0613-1000"].available is False


@pytest.mark.parametrize(
    "listing,slot,email,msg",
    [
        ("L-103", "S-101-0613-1000", "maya.chen@example.com", "pending"),
        ("L-101", "S-101-0613-1000", "sam.okafor@example.com", "no signed buyer agreement"),
        ("L-104", "S-104-0613-1000", "maya.chen@example.com", "no longer available"),
        ("L-101", "S-104-0613-1300", "maya.chen@example.com", "does not belong"),
    ],
)
def test_booking_refused(store, listing, slot, email, msg):
    with pytest.raises(BookingError, match=msg):
        store.book(listing, slot, email)


def test_find_listings_ambiguous_oak(store):
    ids = {r["listing_id"] for r in store.find_listings("blue house on Oak")}
    assert {"L-101", "L-102"} <= ids


def test_escalation_routes_to_listing_agent(store):
    esc = store.escalate("offer", "Buyer wants to offer", "L-102")
    assert esc.assigned_agent_id == "A-2"
    assert store.escalate("other", "no listing").assigned_agent_id == "A-0"
