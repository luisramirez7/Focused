import json
from types import SimpleNamespace

import pytest

from inbox_agent import tools as T
from inbox_agent.faults import FaultPlan, TransientToolError


def rt(plan=None):
    return SimpleNamespace(context=T.RunContext(fault_plan=FaultPlan(plan)))


def call(tool, runtime=None, **kwargs):
    return tool.func(**kwargs, runtime=runtime or rt())


def test_happy_paths(store, fake_kb):
    assert json.loads(call(T.search_listings, query="Willow"))[0]["listing_id"] == "L-104"
    assert json.loads(call(T.get_listing, listing_id="L-101"))["hoa_fee_monthly"] == 285
    assert json.loads(call(T.get_contact, email="maya.chen@example.com"))["known"] is True
    assert json.loads(call(T.check_availability, listing_id="L-104", date="2026-06-13"))
    assert len(json.loads(call(T.search_knowledge_base, query="showing hours"))) == 4


def test_business_errors(store):
    assert call(T.get_listing, listing_id="L-999").startswith("ERROR: listing L-999 not found")
    assert "pending" in call(T.check_availability, listing_id="L-103")
    out = call(
        T.book_showing,
        listing_id="L-101",
        slot_id="S-101-0613-1000",
        contact_email="sam.okafor@example.com",
    )
    assert out.startswith("ERROR") and "buyer agreement" in out


def test_fault_injection(store):
    with pytest.raises(TransientToolError):
        call(T.get_listing, rt({"get_listing": ["timeout"]}), listing_id="L-101")
    assert call(T.search_listings, rt({"search_listings": ["empty"]}), query="Oak") == "[]"
    assert call(T.get_contact, rt({"get_contact": ["error"]}), email="x@y.com").startswith("ERROR")


def test_no_tool_leaks_confidential_notes(store, fake_kb, confidential_strings):
    outputs = [call(T.get_listing, listing_id=lid) for lid in store.listings]
    outputs += [call(T.search_listings, query=q) for q in ["Oak", "Harborview", "condo"]]
    blob = "\n".join(outputs)
    for secret in confidential_strings:
        assert secret not in blob
