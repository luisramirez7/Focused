import pytest

from inbox_agent.faults import FaultPlan, TransientToolError, apply_fault


def test_faults_consumed_in_order_then_ok():
    plan = FaultPlan({"get_listing": ["empty", "error"]})
    assert plan.next("get_listing") == "empty"
    assert plan.next("get_listing") == "error"
    assert plan.next("get_listing") == "ok"
    assert plan.next("other_tool") == "ok"


def test_timeout_raises_transient():
    with pytest.raises(TransientToolError):
        apply_fault("x", FaultPlan({"x": ["timeout"]}))


def test_invalid_fault_rejected():
    with pytest.raises(ValueError):
        FaultPlan({"x": ["explode"]})
