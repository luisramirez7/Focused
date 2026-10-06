"""LangGraph Studio entry point (`uv run langgraph dev`, see langgraph.json).

Wraps the inbox agent in a parent graph whose input is an `Email`, so Studio runs start from the
same prompt `run_email` builds. The agent is mounted as a subgraph without its own checkpointer;
the Studio server persists threads and resumes `book_showing` approvals from the UI.

Imports are absolute because the server loads this file by path, outside the package.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Annotated, Any

from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from inbox_agent.agent import build_agent
from inbox_agent.config import settings
from inbox_agent.schemas import Email, Outcome
from inbox_agent.tools import RunContext

STUDIO_SENDER = "studio.sender@example.com"  # not in contacts, so it takes the unknown-sender path
STUDIO_RECEIVED_AT = "2026-06-08T09:15:00-07:00"  # same "today" as data/emails, so slots line up
_HEADER = re.compile(r"^(from|subject):\s*(.*)$", re.IGNORECASE)
_ADDRESS = re.compile(r"^(?:(.*?)\s*<)?([^<>\s]+@[^<>\s]+)>?$")


class StudioInput(TypedDict):
    email: Email | str


def _email_from_text(text: str) -> Email:
    """Plain text from Studio: optional `From:` / `Subject:` lines, then the body."""
    fields: dict[str, Any] = {"from_address": STUDIO_SENDER}
    lines = text.strip().splitlines()
    while lines and (header := _HEADER.match(lines[0].strip())):
        key, value = header.group(1).lower(), header.group(2).strip()
        if key == "subject":
            fields["subject"] = value
        elif address := _ADDRESS.match(value):
            fields["from_name"] = address.group(1) or None
            fields["from_address"] = address.group(2)
        lines.pop(0)
    return Email(
        email_id=f"studio-{uuid.uuid4().hex[:8]}",
        body="\n".join(lines).strip(),
        received_at=STUDIO_RECEIVED_AT,
        **fields,
    )


def to_email(value: Any) -> Email:
    """Accept an Email, its JSON (object or string), or plain email text."""
    if value is None:
        raise ValueError(
            'Studio input needs an "email" key: {"email": {...a data/emails/*.json file...}} '
            "or plain email text."
        )
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return _email_from_text(value)
        if isinstance(value, dict) and "email" in value:  # the whole input pasted into the field
            value = value["email"]
    return Email.model_validate(value)


class StudioOutput(TypedDict, total=False):
    messages: list[AnyMessage]
    structured_response: Outcome


class StudioState(StudioInput, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    structured_response: Outcome


def ingest_email(state: StudioState) -> dict[str, Any]:
    email = to_email(state.get("email"))
    return {"messages": [HumanMessage(email.as_prompt())]}


def build_studio_graph(model_name=None, model=None):
    agent = build_agent(model_name or settings().agent_model, model=model, checkpointer=None)
    builder = StateGraph(
        StudioState, input_schema=StudioInput, output_schema=StudioOutput, context_schema=RunContext
    )
    builder.add_node("ingest_email", ingest_email)
    builder.add_node("agent", agent)
    builder.add_edge(START, "ingest_email")
    builder.add_edge("ingest_email", "agent")
    builder.add_edge("agent", END)
    return builder.compile(name="rei-inbox-agent-studio")


def make_graph():
    """Factory for langgraph.json, so importing this module never needs API keys."""
    return build_studio_graph()
