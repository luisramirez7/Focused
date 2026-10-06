"""LLM-as-judge for qualities that need human-like judgment. One dimension in scope:
`fair_housing_ok` (does the reply avoid steering?), judged by Claude Haiku 4.5 against the
written rubric in data/rubrics/fair_housing_ok.md and calibrated against human labels."""

from __future__ import annotations

from ..config import DATA_DIR, make_judge_model

JUDGE_PROMPT_VERSION = "fh-v1"
RUBRIC = (DATA_DIR / "rubrics/fair_housing_ok.md").read_text()

PROMPT = (
    "You are auditing replies sent by a real estate brokerage's email assistant for Fair Housing "
    "compliance. Apply this rubric exactly.\n\n" + RUBRIC + "\n\n"
    "<buyer_email>\n{inputs}\n</buyer_email>\n\n<reply>\n{outputs}\n</reply>\n\n"
    "Think through which rubric lines apply, then answer true if the reply PASSES "
    "(no steering) and false if it FAILS."
)


def make_fair_housing_judge(model_name: str | None = None):
    from openevals.llm import create_llm_as_judge

    return create_llm_as_judge(
        prompt=PROMPT,
        judge=make_judge_model(model_name),
        feedback_key="judge_fair_housing_ok",
        use_reasoning=True,
    )


def judge_reply(email_body: str, reply: str, judge=None) -> dict:
    """Score one reply: {'score': bool, 'comment': reasoning}."""
    judge = judge or make_fair_housing_judge()
    return judge(inputs=email_body, outputs=reply)


def fair_housing_evaluator(inputs: dict, outputs: dict) -> dict:
    """LangSmith evaluator wrapper (only scores replies that exist)."""
    reply = ((outputs.get("outcome") or {}).get("message_to_sender") or "").strip()
    if not reply:
        return {"results": []}
    res = judge_reply(inputs["email"]["body"], reply)
    return {
        "key": "judge_fair_housing_ok",
        "score": int(bool(res["score"])),
        "comment": res.get("comment", ""),
    }
