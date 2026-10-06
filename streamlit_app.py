"""Streamlit demo: run the inbox agent on one email (with coordinator approval) and browse evals.

uv sync --extra ui && uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from langchain_anthropic import ChatAnthropic
from langgraph.types import Command

from inbox_agent.agent import RunResult, _summarize, build_agent, get_agent
from inbox_agent.config import DATA_DIR, ConfigError, make_agent_model
from inbox_agent.faults import FaultPlan
from inbox_agent.schemas import Email
from inbox_agent.store import get_store
from inbox_agent.tools import RunContext
from inbox_agent.tracing import run_config, tracing_scope

EMAILS_DIR = DATA_DIR / "emails"
RAW_DIR = Path(__file__).parent / "reports" / "raw"
OUTCOME_COLORS = {
    "reply": "green",
    "propose_booking": "blue",
    "clarify": "orange",
    "escalate": "red",
}

st.set_page_config(page_title="Harborview Inbox Agent", page_icon="🏠", layout="wide")


def samples() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(EMAILS_DIR.glob("*.json"))}


# --- agent run: streamed into the page, split across reruns at the coordinator approval -----

OUTCOME_TOOL = "Outcome"
REPLY_FIELD = re.compile(r'"message_to_sender"\s*:\s*"')
ESCAPES = {"n": "\n", "t": "\t", "r": "", "b": "\b", "f": "\f"}


class EagerToolStreamingAnthropic(ChatAnthropic):
    """Claude with `eager_input_streaming` on every custom tool.

    Without it the API buffers a tool call's input and sends it in one burst, and the reply is a
    tool call (the Outcome schema), so it would appear all at once. UI-only: the evaluated agent
    is unchanged, and eval runs don't stream.
    """

    def _get_request_payload(self, *args, **kwargs) -> dict:
        payload = super()._get_request_payload(*args, **kwargs)
        for tool in payload.get("tools", []):
            if "input_schema" in tool:
                tool["eager_input_streaming"] = True
        return payload


@st.cache_resource
def ui_agent(model_name: str):
    if model_name != "claude":
        return get_agent(model_name)
    base = make_agent_model("claude")
    model = EagerToolStreamingAnthropic(
        **{k: getattr(base, k) for k in base.model_fields_set if k != "profile"}
    )
    return build_agent("claude", model=model)


def new_run(email: Email, model: str, fault_plan: dict | None) -> dict:
    config = run_config(model, "streamlit", thread_id=str(uuid.uuid4()))
    config["metadata"]["email_id"] = email.email_id
    return {
        "model": model,
        "config": config,
        "context": RunContext(sender_email=email.from_address, fault_plan=FaultPlan(fault_plan)),
        "events": {},
        "pending": None,
        "approvals": [],
        "result": None,
        "elapsed": 0.0,
        "payload": {"messages": [{"role": "user", "content": email.as_prompt()}]},
    }


def partial_reply(args_json: str) -> str:
    """`message_to_sender` from a partially streamed Outcome tool call, as far as it has got."""
    m = REPLY_FIELD.search(args_json)
    if not m:
        return ""
    raw, out, i = args_json[m.end() :], [], 0
    while i < len(raw) and raw[i] != '"':
        if raw[i] != "\\":
            out.append(raw[i])
            i += 1
        elif i + 1 >= len(raw):
            break  # escape split across chunks
        elif raw[i + 1] == "u":
            if i + 6 > len(raw):
                break
            out.append(chr(int(raw[i + 2 : i + 6], 16)))
            i += 6
        else:
            out.append(ESCAPES.get(raw[i + 1], raw[i + 1]))
            i += 2
    return "".join(out)


def step_label(tc: dict, note: str = "") -> str:
    args = ", ".join(str(v) for v in tc["args"].values())
    args = args if len(args) <= 60 else args[:59] + "…"
    return f"`{tc['name']}` {args}" + (f" · {note}" if note else "")


def draw(m, steps, open_steps: dict) -> None:
    """Add a step for each tool call; fill it in and close it when the tool result arrives."""
    kind = type(m).__name__
    if kind == "AIMessage":
        for tc in m.tool_calls:
            if tc["name"] == OUTCOME_TOOL or tc["id"] in open_steps:
                continue  # the approval middleware re-emits the paused AIMessage
            with steps:
                status = st.status(step_label(tc), type="step", state="running")
            with status:
                st.caption("arguments")
                st.json(tc["args"])
            open_steps[tc["id"]] = (status, tc)
    elif kind == "ToolMessage" and m.tool_call_id in open_steps:
        status, tc = open_steps.pop(m.tool_call_id)
        content = str(m.content)
        failed = content.startswith("ERROR")
        with status:
            st.caption("result")
            try:
                st.json(json.loads(content))
            except (json.JSONDecodeError, TypeError):
                st.code(content, language=None, wrap_lines=True)
        status.update(label=step_label(tc), state="error" if failed else "complete")


def stream_run(run: dict, payload, steps, open_steps: dict, live) -> None:
    """Stream until the agent finishes or pauses on a booking that needs approval."""
    agent = ui_agent(run["model"])
    started = time.perf_counter()
    run["pending"] = None
    tool_names: dict[tuple, str] = {}
    outcome_json: dict[tuple, str] = {}
    try:
        with tracing_scope(), st.spinner("Agent working…"):
            for mode, data in agent.stream(
                payload,
                run["config"],
                context=run["context"],
                stream_mode=["updates", "messages"],
            ):
                if mode == "messages":
                    chunk = data[0]
                    for tcc in getattr(chunk, "tool_call_chunks", None) or []:
                        key = (chunk.id, tcc.get("index"))
                        if tcc.get("name"):
                            tool_names[key] = tcc["name"]
                        if tool_names.get(key) == OUTCOME_TOOL and tcc.get("args"):
                            # a retried Outcome (validation error) streams under a new key
                            outcome_json[key] = outcome_json.get(key, "") + tcc["args"]
                            if text := partial_reply(outcome_json[key]):
                                live.container(border=True).markdown(
                                    text.replace("\n", "  \n") + " ▌"
                                )
                elif "__interrupt__" in data:
                    run["pending"] = data["__interrupt__"][0].value.get("action_requests", [])
                else:
                    for update in data.values():
                        if not isinstance(update, dict):
                            continue
                        for m in update.get("messages", []) or []:
                            run["events"][m.id or uuid.uuid4().hex] = m
                            draw(m, steps, open_steps)
    except Exception as e:  # shown in the UI rather than crashing the page
        run["elapsed"] += time.perf_counter() - started
        run["result"] = RunResult(outcome=None, status="error", error=f"{type(e).__name__}: {e}")
        return
    run["elapsed"] += time.perf_counter() - started
    if run["pending"]:
        for status, tc in open_steps.values():
            status.update(label=step_label(tc, "waiting for coordinator"))
        return
    state = agent.get_state(run["config"]).values
    result = RunResult(outcome=None, status="no_outcome", approvals=run["approvals"])
    _summarize(state.get("messages", []), result)
    if state.get("structured_response") is not None:
        result.outcome = state["structured_response"].model_dump()
        result.status = "completed"
    result.latency_s = round(run["elapsed"], 2)
    run["result"] = result


# --- rendering -------------------------------------------------------------------------------


def render_approval(requests: list[dict]) -> None:
    store = get_store()
    with st.container(border=True):
        st.markdown("#### ⏸️ Showing booking needs coordinator approval")
        decisions, ok = [], True
        for i, req in enumerate(requests):
            args = req.get("args", {})
            listing = store.get_listing(args.get("listing_id", "")) or {}
            slot = store.slots.get(args.get("slot_id", ""))
            when = slot.start.strftime("%a %b %d, %I:%M %p") if slot else "?"
            st.markdown(
                f"**Listing** {args.get('listing_id', '?')} · {listing.get('address', '?')}  \n"
                f"**Slot** {args.get('slot_id', '?')} · {when}  \n"
                f"**Buyer** {args.get('contact_email', '?')}"
            )
            choice = st.radio(
                "Decision", ["Approve", "Edit slot", "Reject"], horizontal=True, key=f"choice{i}"
            )
            if choice == "Approve":
                decisions.append({"type": "approve"})
            elif choice == "Reject":
                reason = st.text_input("Reason", "Coordinator rejected this booking.", key=f"r{i}")
                decisions.append({"type": "reject", "message": reason})
            else:
                open_slots = store.open_slots(args.get("listing_id", ""))
                if not open_slots:
                    st.warning("No other open slots for this listing.")
                    ok = False
                    continue
                new = st.selectbox(
                    "New slot",
                    open_slots,
                    key=f"s{i}",
                    format_func=lambda s: f"{s['slot_id']} — {s['start']}",
                )
                decisions.append(
                    {
                        "type": "edit",
                        "edited_action": {
                            "name": req["name"],
                            "args": {**args, "slot_id": new["slot_id"]},
                        },
                    }
                )
        if st.button("Submit decision", type="primary", disabled=not ok):
            run = st.session_state.run
            run["approvals"].extend(
                {"request": r, "decision": d} for r, d in zip(requests, decisions, strict=True)
            )
            run["pending"] = None
            run["payload"] = Command(resume={"decisions": decisions})
            st.rerun()


def render_outcome(result: RunResult) -> None:
    if result.outcome is None:
        st.error(f"No outcome — status `{result.status}`\n\n{result.error or ''}")
        return
    o = result.outcome
    color = OUTCOME_COLORS.get(o["outcome"], "gray")
    st.markdown(f"#### Outcome: :{color}-background[{o['outcome']}]")
    with st.container(border=True):
        st.caption("Reply to sender")
        st.markdown(o["message_to_sender"].replace("\n", "  \n"))
    tools = sum(1 for t in result.tool_calls if t["name"] != "Outcome")
    st.caption(
        f"{tools} tool calls · {result.latency_s}s agent time · tokens in/out "
        f"{result.usage['input_tokens']:,}/{result.usage['output_tokens']:,} · citations: "
        f"{', '.join(o['citations']) or '—'}"
    )
    if o.get("escalation"):
        e = o["escalation"]
        st.warning(f"**Escalated · {e['reason_category']}** — {e['internal_note']}")
    if result.booking:
        st.success(f"**Booked** {result.booking}")
    for a in result.approvals:
        st.caption(f"Coordinator decision: `{a['decision']['type']}`")


def inbox_tab() -> None:
    emails = samples()
    left, right = st.columns([2, 3], gap="large")
    with left:
        st.subheader("Inbound email")
        sample = st.selectbox(
            "Sample",
            ["(write your own)", *emails],
            index=1 + list(emails).index("showing-saturday") if "showing-saturday" in emails else 0,
        )
        d = emails.get(sample, {})
        from_address = st.text_input("From", d.get("from_address", "maya.chen@example.com"))
        from_name = st.text_input("Name", d.get("from_name") or "")
        subject = st.text_input("Subject", d.get("subject", ""))
        body = st.text_area("Body", d.get("body", ""), height=180)
        with st.expander("Inject tool faults"):
            fault = st.text_input(
                "Fault plan JSON",
                "",
                placeholder='{"get_listing": ["timeout", "timeout", "timeout"]}',
            )
        if st.button("Run agent", type="primary", disabled=not body.strip()):
            try:
                email = Email(
                    email_id=d.get("email_id", "UI-" + uuid.uuid4().hex[:6]),
                    from_address=from_address,
                    from_name=from_name or None,
                    subject=subject,
                    body=body,
                    received_at=d.get("received_at") or datetime.now().astimezone(),
                )
                st.session_state.run = new_run(
                    email, st.session_state.model, json.loads(fault) if fault else None
                )
            except (ValueError, ConfigError) as e:
                st.error(str(e))
    with right:
        run = st.session_state.get("run")
        if not run:
            st.info(
                "Pick a sample email and press **Run agent**. Bookings pause here for your "
                "approval, just like the coordinator in the CLI."
            )
            return
        st.subheader("Trajectory")
        steps = st.container()
        open_steps: dict = {}
        for m in run["events"].values():  # replay what earlier reruns streamed
            draw(m, steps, open_steps)
        for status, tc in open_steps.values():
            status.update(label=step_label(tc, "waiting for coordinator"))
        live = st.empty()
        if (payload := run.pop("payload", None)) is not None:
            stream_run(run, payload, steps, open_steps, live)
            live.empty()
        if run["pending"]:
            render_approval(run["pending"])
        elif run["result"]:
            render_outcome(run["result"])


# --- eval browser ----------------------------------------------------------------------------

CHECKS = [
    "outcome_correct",
    "no_forbidden_tool",
    "forbidden_absent",
    "facts_present",
    "citations_valid",
    "numeric_claims_grounded",
    "tools_expected_called",
    "tool_args_correct",
    "escalation_reason_correct",
    "no_unapproved_booking",
    "pii_absent_in_reply",
    "within_budgets",
]


@st.cache_data
def load_raw(path: str) -> pd.DataFrame:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    out = []
    for r in rows:
        outcome = (r.get("outputs.outcome") or {}).get("outcome")
        expected = r.get("reference.expected_outcome")
        failed = [c for c in CHECKS if r.get(f"feedback.{c}") not in (None, 1, 1.0, True)]
        out.append(
            {
                "email": r["inputs.email"]["email_id"],
                "split": r.get("split"),
                "slice": ", ".join(r.get("slices") or []),
                "expected": expected,
                "actual": outcome,
                "over_escalated": outcome == "escalate" and expected != "escalate",
                "tool_calls": sum(
                    1 for t in r.get("outputs.tool_calls") or [] if t["name"] != "Outcome"
                ),
                "failed_checks": ", ".join(failed),
                "latency_s": r.get("outputs.latency_s"),
                "_row": r,
            }
        )
    return pd.DataFrame(out)


def evals_tab() -> None:
    files = sorted(RAW_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("No raw experiment files in reports/raw/.")
        return
    f = st.selectbox("Experiment", files, format_func=lambda p: p.stem)
    df = load_raw(str(f))
    c1, c2, c3 = st.columns(3)
    splits = c1.multiselect("Split", sorted(df.split.dropna().unique()))
    slices = c2.multiselect("Slice", sorted({s for x in df.slice for s in x.split(", ") if s}))
    only_fail = c3.toggle("Only runs with a failed check or over-escalation")
    view = df
    if splits:
        view = view[view.split.isin(splits)]
    if slices:
        view = view[view.slice.apply(lambda x: any(s in x for s in slices))]
    if only_fail:
        view = view[(view.failed_checks != "") | view.over_escalated]

    m = st.columns(5)
    m[0].metric("Runs", len(view))
    m[1].metric("Strict outcome match", f"{(view.expected == view.actual).mean():.0%}")
    m[2].metric("Over-escalation", f"{view.over_escalated.mean():.0%}")
    m[3].metric("Tool calls / email", f"{view.tool_calls.mean():.1f}")
    m[4].metric("Latency p50", f"{view.latency_s.median():.1f}s")

    st.caption("Confusion matrix: expected (rows) × actual (columns)")
    st.dataframe(pd.crosstab(view.expected, view.actual.fillna("none")), use_container_width=False)

    event = st.dataframe(
        view.drop(columns="_row"),
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
    )
    picked = event.selection.rows
    if picked:
        r = view.iloc[picked[0]]["_row"]
        e = r["inputs.email"]
        with st.container(border=True):
            st.markdown(
                f"**{e['email_id']}** · {e.get('from_name') or ''} <{e['from_address']}> · "
                f"_{e.get('subject', '')}_"
            )
            st.code(e["body"], language=None, wrap_lines=True)
            o = r.get("outputs.outcome") or {}
            st.markdown(
                f"Agent: **{o.get('outcome')}** · expected **"
                f"{r.get('reference.expected_outcome')}** (acceptable: "
                f"{', '.join(r.get('reference.acceptable_outcomes') or [])})"
            )
            st.markdown((o.get("message_to_sender") or "").replace("\n", "  \n"))
            st.caption("Tool calls")
            st.json(
                [
                    {"name": t["name"], "args": t["args"], "status": t["status"]}
                    for t in r.get("outputs.tool_calls") or []
                    if t["name"] != "Outcome"
                ],
                expanded=False,
            )
            st.caption("Feedback")
            st.json(
                {
                    k.removeprefix("feedback."): v
                    for k, v in r.items()
                    if k.startswith("feedback.") and v is not None
                },
                expanded=False,
            )


# --- page ------------------------------------------------------------------------------------

with st.sidebar:
    st.title("🏠 Harborview")
    st.caption("Inbound buyer email → reply · propose_booking · clarify · escalate")
    st.session_state.model = st.radio("Model", ["claude", "glm"], horizontal=True)
    if st.button("Reset bookings & escalations"):
        get_store().reset()
        st.session_state.pop("run", None)
        st.toast("Store reset")
    store = get_store()
    st.metric("Bookings this session", len(store.bookings))
    st.metric("Escalations this session", len(store.escalations))

inbox, evals = st.tabs(["Inbox", "Eval results"])
with inbox:
    inbox_tab()
with evals:
    evals_tab()
