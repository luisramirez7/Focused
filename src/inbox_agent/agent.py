"""Agent wiring and the single entry point `run_email` used by the CLI and the evaluations."""

from __future__ import annotations

import json
import re
import time
import uuid
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from .config import AgentModelName, make_agent_model
from .faults import FaultPlan, TransientToolError
from .pii import build_pii_middleware
from .prompts import SYSTEM_PROMPT
from .schemas import Email, Outcome
from .store import get_store
from .tools import TOOL_BUDGETS, TOOLS, RunContext
from .tracing import run_config, tracing_scope

# Expected with Claude + adaptive thinking (research R3): langchain drops the forced tool_choice.
warnings.filterwarnings("ignore", message="tool_choice is forced but thinking is enabled")

LISTING_ID = re.compile(r"\bL-\d{3}\b")
OUTCOME_TOOL = "Outcome"

# Decision for a pending booking: {"type": "approve"} | {"type": "reject", "message": ...} |
# {"type": "edit", "edited_action": {"name": ..., "args": {...}}}
InterruptHandler = Callable[[dict], dict]
EventHandler = Callable[[str, Any], None]


def _retry_exhausted(exc: Exception) -> str:
    return (
        f"ERROR: tool temporarily unavailable after retries ({exc}). "
        "Do not guess the missing information; consider escalating with reason tool_failure."
    )


def _tool_error(exc: Exception, request) -> str:
    name = request.tool.name if request.tool else request.tool_call["name"]
    return f"ERROR: {name} failed unexpectedly ({type(exc).__name__}). Consider escalating."


def build_middleware() -> list:
    return [
        *build_pii_middleware(),
        HumanInTheLoopMiddleware(
            interrupt_on={"book_showing": {"allowed_decisions": ["approve", "edit", "reject"]}},
            description_prefix="Showing booking requires coordinator approval",
        ),
        ToolErrorMiddleware(on_error=_tool_error),
        ToolRetryMiddleware(
            max_retries=2,
            retry_on=(TransientToolError,),
            on_failure=_retry_exhausted,
            backoff_factor=2.0,
            initial_delay=0.2,
            max_delay=2.0,
            jitter=True,
        ),
        *[
            ToolCallLimitMiddleware(tool_name=name, run_limit=limit, exit_behavior="continue")
            for name, limit in TOOL_BUDGETS.items()
        ],
        ModelCallLimitMiddleware(run_limit=12, exit_behavior="end"),
    ]


def build_agent(model_name: AgentModelName, model=None):
    return create_agent(
        model or make_agent_model(model_name),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        middleware=build_middleware(),
        response_format=ToolStrategy(Outcome, handle_errors=True),
        context_schema=RunContext,
        checkpointer=InMemorySaver(
            serde=JsonPlusSerializer(
                allowed_msgpack_modules=[
                    ("inbox_agent.schemas", "Outcome"),
                    ("inbox_agent.schemas", "EscalationDetail"),
                    ("inbox_agent.schemas", "BookingProposalRef"),
                ]
            )
        ),
        name="rei-inbox-agent",
    )


_agents: dict[str, Any] = {}


def get_agent(model_name: AgentModelName):
    if model_name not in _agents:
        _agents[model_name] = build_agent(model_name)
    return _agents[model_name]


# --- run result -----------------------------------------------------------------------------


@dataclass
class RunResult:
    outcome: dict | None
    status: str  # completed | no_outcome | step_limit | error
    tool_calls: list[dict] = field(default_factory=list)
    retrieved_doc_ids: list[str] = field(default_factory=list)
    listing_ids_seen: list[str] = field(default_factory=list)
    tool_outputs: list[str] = field(default_factory=list)
    model_inputs: list[str] = field(default_factory=list)
    booking: dict | None = None
    escalation_id: str | None = None
    approvals: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    latency_s: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _decision_for(policy: str | None, request: dict) -> dict:
    if policy == "approve":
        return {"type": "approve"}
    if policy == "reject":
        return {"type": "reject", "message": "The coordinator rejected this booking."}
    if policy and policy.startswith("edit:"):
        args = dict(request.get("args", {}))
        args["slot_id"] = policy.split(":", 1)[1]
        return {"type": "edit", "edited_action": {"name": request["name"], "args": args}}
    raise ValueError(f"No approval policy or handler for booking request: {request}")


def _serialize(msg) -> dict:
    if isinstance(msg, AIMessage):
        return {
            "role": "assistant",
            "content": msg.text,
            "tool_calls": [
                {"name": tc["name"], "args": tc["args"], "id": tc["id"]} for tc in msg.tool_calls
            ],
        }
    if isinstance(msg, ToolMessage):
        return {
            "role": "tool",
            "name": msg.name,
            "content": str(msg.content),
            "tool_call_id": msg.tool_call_id,
            "status": getattr(msg, "status", "success"),
        }
    if isinstance(msg, HumanMessage):
        return {"role": "user", "content": str(msg.content)}
    return {"role": getattr(msg, "type", "other"), "content": str(getattr(msg, "content", ""))}


def _summarize(messages: list, result: RunResult) -> None:
    status_by_id: dict[str, str] = {}
    for m in messages:
        if isinstance(m, ToolMessage):
            status_by_id[m.tool_call_id] = getattr(m, "status", "success") or "success"
            content = str(m.content)
            result.tool_outputs.append(content)
            result.listing_ids_seen.extend(LISTING_ID.findall(content))
            if m.name == "search_knowledge_base":
                try:
                    result.retrieved_doc_ids.extend(d["doc_id"] for d in json.loads(content))
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass
            if m.name == "book_showing" and not content.startswith("ERROR"):
                try:
                    result.booking = json.loads(content)
                except json.JSONDecodeError:
                    pass
            if m.name == "escalate_to_agent" and not content.startswith("ERROR"):
                try:
                    result.escalation_id = json.loads(content)["escalation_id"]
                except (json.JSONDecodeError, KeyError):
                    pass
        elif isinstance(m, HumanMessage):
            result.model_inputs.append(str(m.content))
        elif isinstance(m, AIMessage):
            usage = m.usage_metadata or {}
            result.usage["input_tokens"] += usage.get("input_tokens", 0)
            result.usage["output_tokens"] += usage.get("output_tokens", 0)
    for m in messages:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls:
                result.tool_calls.append(
                    {
                        "name": tc["name"],
                        "args": tc["args"],
                        "status": status_by_id.get(tc["id"], "success"),
                    }
                )
    result.retrieved_doc_ids = list(dict.fromkeys(result.retrieved_doc_ids))
    result.listing_ids_seen = list(dict.fromkeys(result.listing_ids_seen))
    result.messages = [_serialize(m) for m in messages]


def run_email(
    email: Email,
    *,
    model_name: AgentModelName,
    fault_plan: FaultPlan | dict | None = None,
    approval_policy: str | None = None,
    on_interrupt: InterruptHandler | None = None,
    on_event: EventHandler | None = None,
    variant: str = "dev",
    agent=None,
    reset_store: bool = False,
) -> RunResult:
    """Handle one email end to end and return a RunResult (contracts/outcome.md)."""
    if reset_store:
        get_store().reset()
    agent = agent or get_agent(model_name)
    plan = fault_plan if isinstance(fault_plan, FaultPlan) else FaultPlan(fault_plan)
    decided_by = {"approve": "auto-approve", "reject": "auto-reject"}.get(
        (approval_policy or "").split(":")[0], "coordinator"
    )
    context = RunContext(sender_email=email.from_address, fault_plan=plan, decided_by=decided_by)
    config = run_config(model_name, variant, thread_id=str(uuid.uuid4()))
    config["metadata"]["email_id"] = email.email_id

    result = RunResult(outcome=None, status="error")
    payload: Any = {"messages": [{"role": "user", "content": email.as_prompt()}]}
    started = time.perf_counter()
    try:
        with tracing_scope():
            while True:
                interrupt = None
                for chunk in agent.stream(payload, config, context=context, stream_mode="updates"):
                    if "__interrupt__" in chunk:
                        interrupt = chunk["__interrupt__"][0].value
                    elif on_event:
                        for node, update in chunk.items():
                            on_event(node, update)
                if interrupt is None:
                    break
                decisions = []
                for request in interrupt.get("action_requests", []):
                    decision = (
                        on_interrupt(request)
                        if on_interrupt
                        else _decision_for(approval_policy, request)
                    )
                    decisions.append(decision)
                    result.approvals.append({"request": request, "decision": decision})
                payload = Command(resume={"decisions": decisions})
        state = agent.get_state(config).values
        messages = state.get("messages", [])
        _summarize(messages, result)
        structured = state.get("structured_response")
        if structured is not None:
            result.outcome = structured.model_dump()
            result.status = "completed"
        elif any(
            "limit" in (m.text or "").lower() for m in messages[-2:] if isinstance(m, AIMessage)
        ):
            result.status = "step_limit"
        else:
            result.status = "no_outcome"
    except GraphRecursionError as e:
        result.status, result.error = "step_limit", str(e)
    except Exception as e:  # surfaced in RunResult so evals score it instead of crashing
        result.status, result.error = "error", f"{type(e).__name__}: {e}"
    result.latency_s = round(time.perf_counter() - started, 3)
    return result
