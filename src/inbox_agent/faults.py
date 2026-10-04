"""Fault injection for evaluating resilience (research R13, FR-022).

A FaultPlan maps a tool name to a queue of faults consumed one per call. When a tool's queue is
exhausted, calls succeed normally.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

Fault = Literal["ok", "timeout", "error", "empty", "malformed"]
VALID_FAULTS: frozenset[str] = frozenset({"ok", "timeout", "error", "empty", "malformed"})


class TransientToolError(Exception):
    """A temporary failure (e.g. timeout). Retried by ToolRetryMiddleware."""


class FaultPlan:
    def __init__(self, plan: Mapping[str, list[str]] | None = None):
        plan = dict(plan or {})
        for tool, faults in plan.items():
            bad = [f for f in faults if f not in VALID_FAULTS]
            if bad:
                raise ValueError(f"Unknown fault(s) {bad} for tool {tool!r}")
        self._queues: dict[str, list[str]] = {k: list(v) for k, v in plan.items()}

    def next(self, tool_name: str) -> Fault:
        queue = self._queues.get(tool_name)
        if not queue:
            return "ok"
        return queue.pop(0)  # type: ignore[return-value]

    def to_dict(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._queues.items()}

    def __bool__(self) -> bool:
        return any(self._queues.values())


def apply_fault(tool_name: str, plan: FaultPlan | None) -> Fault:
    """Consume the next fault for this tool. Raises TransientToolError for timeouts."""
    fault = plan.next(tool_name) if plan else "ok"
    if fault == "timeout":
        raise TransientToolError(f"{tool_name} timed out")
    return fault
