"""Evaluation targets: what gets run for each example at each evaluation level."""

from __future__ import annotations

import uuid

from langchain_core.messages import AIMessage

from ..agent import get_agent, run_email
from ..config import AgentModelName
from ..faults import FaultPlan
from ..retrieval import search
from ..schemas import Email
from ..tools import RunContext
from ..tracing import run_config, tracing_scope


def full_run_target(model: AgentModelName, variant: str):
    """Level 3–5: the whole agent, with the example's fault plan and approval policy."""

    def target(inputs: dict) -> dict:
        email = Email(**inputs["email"])
        result = run_email(
            email,
            model_name=model,
            fault_plan=inputs.get("fault_plan"),
            approval_policy=inputs.get("approval_policy") or "approve",
            variant=variant,
            reset_store=True,
        )
        return result.to_dict()

    return target


def first_step_target(model: AgentModelName, variant: str):
    """Level 2: only the agent's first decision, using the production prompt and middleware,
    by interrupting right after the first model call."""

    def target(inputs: dict) -> dict:
        email = Email(**inputs["email"])
        agent = get_agent(model)
        config = run_config(model, variant, extra_tags=["first-step"], thread_id=str(uuid.uuid4()))
        context = RunContext(
            sender_email=email.from_address, fault_plan=FaultPlan(inputs.get("fault_plan"))
        )
        with tracing_scope():
            agent.invoke(
                {"messages": [{"role": "user", "content": email.as_prompt()}]},
                config,
                context=context,
                interrupt_after=["model"],
            )
        messages = agent.get_state(config).values.get("messages", [])
        ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
        calls = ai.tool_calls if ai else []
        return {
            "first_tool": calls[0]["name"] if calls else None,
            "first_args": calls[0]["args"] if calls else {},
            "no_tool": not calls,
        }

    return target


def retriever_target(k: int = 4):
    """Level 1: the retriever alone."""

    def target(inputs: dict) -> dict:
        docs = search(inputs["query"], k=k)
        return {
            "doc_ids": list(dict.fromkeys(d["doc_id"] for d in docs)),
            "chunk_ids": [d["chunk_id"] for d in docs],
        }

    return target
