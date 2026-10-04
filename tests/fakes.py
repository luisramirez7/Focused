"""Scripted fake chat model for offline agent tests."""

from __future__ import annotations

import itertools

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

_ids = itertools.count()


def call(name: str, **args) -> dict:
    return {"name": name, "args": args, "id": f"call_{next(_ids)}", "type": "tool_call"}


def ai(*tool_calls: dict, text: str = "") -> AIMessage:
    return AIMessage(content=text, tool_calls=list(tool_calls))


def outcome(kind="reply", message="Thanks!", citations=(), **extra) -> dict:
    return call(
        "Outcome", outcome=kind, message_to_sender=message, citations=list(citations), **extra
    )


class ScriptedModel(GenericFakeChatModel):
    """Returns the scripted AIMessages in order; ignores tool binding."""

    def bind_tools(self, tools, **kwargs):  # noqa: D401
        return self


def scripted(*messages: AIMessage) -> ScriptedModel:
    return ScriptedModel(messages=iter(messages))


def email(body="What are the HOA fees for 42 Oak St?", sender="maya.chen@example.com"):
    from inbox_agent.schemas import Email

    return Email(
        email_id="E-T",
        from_address=sender,
        subject="Question",
        body=body,
        received_at="2026-06-08T09:00:00-07:00",
    )
