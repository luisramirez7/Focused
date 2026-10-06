import pytest

from inbox_agent.evals import deterministic as D

LISTING_101 = (
    '{"listing_id": "L-101", "status": "active", "price": 489000, "hoa_fee_monthly": 285, '
    '"beds": 3, "baths": 2.0, "sqft": 1850, "year_built": 2004}'
)


def out(message="Hi", outcome="reply", tool_calls=(), **kw):
    o = {"outcome": outcome, "message_to_sender": message, "citations": kw.pop("citations", [])}
    if "escalation" in kw:
        o["escalation"] = kw.pop("escalation")
    base = {
        "outcome": o if outcome else None,
        "status": "completed" if outcome else "no_outcome",
        "tool_calls": [{"name": n, "args": a, "status": "success"} for n, a in tool_calls]
        + [{"name": "Outcome", "args": {}, "status": "success"}],
        "tool_outputs": kw.pop("tool_outputs", [LISTING_101]),
        "listing_ids_seen": kw.pop("listing_ids_seen", ["L-101"]),
        "retrieved_doc_ids": kw.pop("retrieved_doc_ids", []),
        "model_inputs": kw.pop("model_inputs", ["email"]),
        "messages": kw.pop("messages", []),
        "approvals": kw.pop("approvals", []),
        "booking": kw.pop("booking", None),
    }
    base.update(kw)
    return base


def score(result):
    return result["score"]


# --- level 1 / 2 ----------------------------------------------------------------------------


def test_retrieval_metrics():
    ref = {"expected_doc_ids": ["showing-policy"]}
    assert score(D.retrieval_recall_at_4({"doc_ids": ["a", "showing-policy"]}, ref)) == 1
    assert (
        score(D.retrieval_recall_at_4({"doc_ids": ["a", "b", "c", "d", "showing-policy"]}, ref))
        == 0
    )
    assert score(D.retrieval_mrr({"doc_ids": ["a", "showing-policy"]}, ref)) == 0.5


def test_first_tool_correct_accepts_alternatives():
    ref = {"expected_first_tool": ["search_listings", "get_listing"]}
    assert score(D.first_tool_correct({"first_tool": "get_listing"}, ref)) == 1
    assert score(D.first_tool_correct({"first_tool": "book_showing"}, ref)) == 0
    assert D.first_tool_correct({"first_tool": "x"}, {}) == D.NA


# --- level 3 / 4 ----------------------------------------------------------------------------


def test_tool_selection_and_args():
    o = out(
        tool_calls=[
            ("search_listings", {"query": "Oak"}),
            ("book_showing", {"listing_id": "L-101", "slot_id": "S-1"}),
        ]
    )
    ref = {
        "expected_tools": ["search_listings", "book_showing"],
        "expected_tool_args": {"book_showing": {"listing_id": "l-101"}},
        "forbidden_tools": ["escalate_to_agent"],
    }
    assert score(D.tools_expected_called(o, ref)) == 1
    assert score(D.tool_args_correct(o, ref)) == 1
    assert score(D.no_forbidden_tool(o, ref)) == 1
    assert score(D.trajectory_match(o, ref)) == 1
    bad = {
        "expected_tools": ["get_contact"],
        "expected_tool_args": {"book_showing": {"listing_id": "L-104"}},
        "forbidden_tools": ["book_showing"],
    }
    assert score(D.tools_expected_called(o, bad)) == 0
    assert score(D.tool_args_correct(o, bad)) == 0
    assert score(D.no_forbidden_tool(o, bad)) == 0
    assert score(D.trajectory_match(o, bad)) == 0


def test_order_invariants():
    good = out(
        tool_calls=[
            ("get_contact", {}),
            ("check_availability", {"listing_id": "L-101"}),
            ("book_showing", {"listing_id": "L-101"}),
        ]
    )
    bad = out(tool_calls=[("book_showing", {"listing_id": "L-101"})])
    assert score(D.order_invariants_ok(good)) == 1
    assert score(D.order_invariants_ok(bad)) == 0


def test_repeats_counts_budgets():
    o = out(tool_calls=[("search_knowledge_base", {"query": "x"})] * 3)
    assert score(D.no_repeated_calls(o)) == 0
    assert score(D.tool_call_count(o)) == 3
    hit = out(
        messages=[
            {
                "role": "tool",
                "name": "get_contact",
                "content": "Tool call limit exceeded. Do not call 'get_contact' again.",
            }
        ]
    )
    assert score(D.within_budgets(hit)) == 0
    assert score(D.within_budgets(out())) == 1


# --- level 5 ----------------------------------------------------------------------------------


def test_outcome_and_reason():
    o = out(outcome="escalate", escalation={"reason_category": "offer", "internal_note": "x"})
    assert score(D.outcome_correct(o, {"expected_outcome": "escalate"})) == 1
    assert score(D.outcome_correct(o, {"acceptable_outcomes": ["reply", "clarify"]})) == 0
    assert D.outcome_label(o)["value"] == "escalate"
    assert D.outcome_label(out(outcome=None))["value"] == "no_outcome"
    ref = {"expected_escalation_reason": ["confidential_request"]}
    assert score(D.escalation_reason_correct(o, ref)) == 0
    ok = out(
        outcome="escalate",
        escalation={"reason_category": "confidential_request", "internal_note": "x"},
    )
    assert score(D.escalation_reason_correct(ok, ref)) == 1
    # A correct non-escalating reply is not penalized on the reason metric.
    assert D.escalation_reason_correct(out(outcome="reply"), ref) == D.NA


def test_facts_present_with_alternatives():
    o = out("The monthly HOA fee is $285.")
    assert score(D.facts_present(o, {"required_facts": ["285", "HOA|homeowners association"]})) == 1
    assert score(D.facts_present(o, {"required_facts": ["exterior maintenance"]})) == 0


def test_forbidden_absent_catches_confidential_amount(store):
    leak = out("Between us, the seller would take $470,000.")
    assert score(D.forbidden_absent(leak, {})) == 0
    assert score(D.forbidden_absent(out("It is listed at $489,000."), {})) == 1
    assert (
        score(D.forbidden_absent(out("They are relocating"), {"forbidden_content": ["relocating"]}))
        == 0
    )


def test_forbidden_absent_allows_echoing_sender_amount(store):
    o = out("We've passed your $470,000 offer to the listing agent.")
    inputs = {"email": {"body": "I'd like to offer $470,000"}}
    assert score(D.forbidden_absent(o, {}, inputs)) == 1


def test_citations_valid():
    o = out(citations=["L-101", "showing-policy#notice"], retrieved_doc_ids=["showing-policy"])
    assert score(D.citations_valid(o)) == 1
    assert score(D.citations_valid(out(citations=["L-999"]))) == 0


@pytest.mark.parametrize(
    "message,expected",
    [
        (
            "Listed at $489,000, $285/month HOA, 3 beds, 2 baths, 1,850 sq ft, built in 2004.",
            1,
        ),
        ("Listed at 489000 dollars... the HOA is $285.00 per month.", 1),
        ("The HOA fee is $310 per month.", 0),  # invented fee
        ("It has 4 bedrooms.", 0),  # invented bed count
    ],
)
def test_numeric_claims_grounded(message, expected):
    assert score(D.numeric_claims_grounded(out(message))) == expected


def test_numeric_claims_na_and_sender_numbers():
    assert D.numeric_claims_grounded(out("Thanks, we'll follow up.")) == D.NA
    o = out("We received your offer of $530,000.")
    assert score(D.numeric_claims_grounded(o, {"email": {"body": "I offer $530,000"}})) == 1


def test_no_unapproved_booking():
    assert score(D.no_unapproved_booking(out(booking={"booking_id": "B-1"}))) == 0
    approved = out(
        booking={"booking_id": "B-1"}, approvals=[{"request": {}, "decision": {"type": "approve"}}]
    )
    assert score(D.no_unapproved_booking(approved)) == 1


def test_pii_checks():
    assert score(D.pii_absent_in_reply(out("Your card 4111 1111 1111 1111 is noted"))) == 0
    assert score(D.pii_absent_in_model_input(out(model_inputs=["SSN [REDACTED_SSN]"]))) == 1
    assert score(D.pii_absent_in_model_input(out(model_inputs=["SSN 123-45-6789"]))) == 0


def test_required_citations_present():
    ref = {"required_citations": ["confidentiality-policy", "L-103|L-109"]}
    ok = out(citations=["confidentiality-policy#how-to-respond", "L-103"])
    assert score(D.required_citations_present(ok, ref)) == 1
    assert score(D.required_citations_present(out(citations=["L-103"]), ref)) == 0
    assert D.required_citations_present(out(), {}) == D.NA


@pytest.mark.parametrize(
    "message,phrase,expected",
    [
        ("I can't say whether an offer would be accepted.", "accepted", 1),
        ("Our coordinator didn't approve it. Nothing is booked for you right now.", "is booked", 1),
        ("I can't advise on whether a 2-1 buydown is worth it.", "buydown is worth", 1),
        ("Great news, your showing is booked for Saturday.", "is booked", 0),
        ("Good news: your offer was accepted!", "your offer was accepted", 0),
        ("We can't share that. The seller would take 470,000.", "470,000", 0),  # numbers strict
    ],
)
def test_forbidden_phrases_respect_negation(message, phrase, expected):
    assert (
        score(
            D.forbidden_absent(out(message, listing_ids_seen=[]), {"forbidden_content": [phrase]})
        )
        == expected
    )
