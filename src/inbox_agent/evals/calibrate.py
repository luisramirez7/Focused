"""Judge calibration for `fair_housing_ok`: humans label replies blind in a LangSmith annotation
queue; the judge scores the same replies; agreement is reported on a held-out split.

The 50 replies live in data/calibration/fair_housing.jsonl (`source` says where each came from):
round 1 is 20 real agent replies to the golden set's Fair Housing emails plus 10 seeded replies
with explicit steering; round 2 is 8 real agent replies to subtler bait emails plus 12 hand-written
replies near the rubric line. The code that generated them is in git history (commit 9283515).

`rei calibrate --push`    queue not-yet-queued replies in `rei-judge-calibration`
`rei calibrate --report`  pull human labels, run the judge, write reports/calibration.md
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from rich.console import Console

from ..config import DATA_DIR, REPORTS_DIR
from . import stats as S

console = Console()
CAL_PATH = DATA_DIR / "calibration" / "fair_housing.jsonl"
PROJECT = "rei-calibration"
QUEUE = "rei-judge-calibration"
KEY = "fair_housing_ok"


def _rows() -> list[dict]:
    return [json.loads(x) for x in CAL_PATH.read_text().splitlines() if x.strip()]


def push() -> str:
    """Log each not-yet-queued reply as a run (no source shown to the labeler) and queue it."""
    from langsmith import Client

    client = Client()
    rows = _rows()
    run_ids = []
    now = datetime.now(UTC)
    for r in rows:
        if r.get("run_id"):
            continue
        rid = uuid.uuid4()
        client.create_run(
            name="fair-housing-calibration",
            run_type="chain",
            project_name=PROJECT,
            id=rid,
            inputs={"buyer_email": r["email"]},
            outputs={"reply": r["reply"]},
            start_time=now,
            end_time=now,
            extra={"metadata": {"cal_id": r["cal_id"]}},
        )
        r["run_id"] = str(rid)
        run_ids.append(rid)
    CAL_PATH.write_text("".join(json.dumps(r) + "\n" for r in rows))
    # The rubric item only attaches if its feedback key already exists.
    if KEY not in {c.feedback_key for c in client.list_feedback_configs()}:
        client.create_feedback_config(
            KEY,
            feedback_config={
                "type": "categorical",
                "categories": [{"value": 1, "label": "Pass"}, {"value": 0, "label": "Fail"}],
            },
        )
    queues = list(client.list_annotation_queues(name=QUEUE))
    queue = (
        queues[0]
        if queues
        else client.create_annotation_queue(
            name=QUEUE,
            description="Blind human labels for calibrating the Fair Housing LLM judge.",
            rubric_instructions=(DATA_DIR / "rubrics/fair_housing_ok.md").read_text(),
            rubric_items=[
                {
                    "feedback_key": KEY,
                    "description": "Pass = the reply avoids steering.",
                    "value_descriptions": {"1": "Pass", "0": "Fail"},
                    "is_required": True,
                }
            ],
        )
    )
    client.flush()
    _enqueue(client, queue.id, run_ids)
    console.print(f"Queued {len(run_ids)} replies in annotation queue [bold]{QUEUE}[/bold].")
    return str(queue.id)


def _enqueue(client, queue_id, run_ids, attempts: int = 12) -> None:
    """Runs are ingested asynchronously; retry until the queue can see them."""
    import time

    from langsmith.utils import LangSmithNotFoundError

    for i in range(attempts):
        try:
            client.add_runs_to_annotation_queue(queue_id, run_ids=run_ids)
            return
        except LangSmithNotFoundError:
            time.sleep(min(2 * (i + 1), 10))
    raise RuntimeError("Runs were not ingested in time; queue them from the LangSmith UI.")


def report(judge_model: str | None = None) -> str:
    from langsmith import Client

    from .judges import JUDGE_PROMPT_VERSION, judge_reply, make_fair_housing_judge

    client = Client()
    rows = [r for r in _rows() if r.get("run_id")]
    human = {}
    ids = [r["run_id"] for r in rows]
    # Batched: run ids go in the query string, and ~50 of them makes LangSmith answer 401.
    for i in range(0, len(ids), 20):
        for fb in client.list_feedback(run_ids=ids[i : i + 20], feedback_key=[KEY]):
            if fb.score is not None:
                human[str(fb.run_id)] = int(fb.score)
    judge = make_fair_housing_judge(judge_model)
    labeled = []
    for r in rows:
        if r["run_id"] not in human:
            continue
        res = judge_reply(r["email"], r["reply"], judge)
        labeled.append(
            {
                **r,
                "human": human[r["run_id"]],
                "judge": int(bool(res["score"])),
                "reason": str(res.get("comment", "")),
            }
        )
    if not labeled:
        console.print("[yellow]No human labels yet.[/yellow]")
        return ""
    lines = [
        f"# Judge calibration: `{KEY}`",
        "",
        f"Judge: Claude Haiku 4.5, prompt `{JUDGE_PROMPT_VERSION}` · rubric "
        "`data/rubrics/fair_housing_ok.md` · labels: blind human review in the LangSmith "
        f"queue `{QUEUE}` · {len(labeled)} labeled replies "
        f"({sum(r['source'] == 'seeded' for r in labeled)} seeded with steering, "
        f"{sum(r['source'] == 'handwritten-borderline' for r in labeled)} hand-written borderline, "
        f"{sum(r['source'].startswith('agent:') for r in labeled)} real agent replies).",
        "",
    ]
    groups = {
        "dev": lambda r: r["split"] == "dev",
        "heldout": lambda r: r["split"] == "heldout",
        "all": lambda r: True,
        "round 1 (explicit seeded + clean real replies)": lambda r: r.get("round", 1) == 1,
        "round 2 (borderline: bait emails + hand-written)": lambda r: r.get("round", 1) == 2,
    }
    for split, keep in groups.items():
        sub = [r for r in labeled if keep(r)]
        if not sub:
            continue
        h, j = [r["human"] for r in sub], [r["judge"] for r in sub]
        acc = sum(a == b for a, b in zip(h, j, strict=True)) / len(sub)
        kappa = S.cohen_kappa(h, j)
        cm = {
            (a, b): sum(1 for x, y in zip(h, j, strict=True) if x == a and y == b)
            for a in (1, 0)
            for b in (1, 0)
        }
        lines += [
            f"## {split} (n = {len(sub)})",
            "",
            f"Accuracy {acc:.0%} · Cohen's kappa {kappa:.2f}",
            "",
            "| human \\ judge | pass | fail |",
            "|---|---|---|",
            f"| pass | {cm[(1, 1)]} | {cm[(1, 0)]} |",
            f"| fail | {cm[(0, 1)]} | {cm[(0, 0)]} |",
            "",
        ]
    dis = [r for r in labeled if r["human"] != r["judge"]]
    lines += ["## Disagreements", ""]
    for r in dis or []:
        lines += [
            f"- **{r['cal_id']}** ({r['split']}, {r['source']}): human "
            f"{'pass' if r['human'] else 'fail'}, judge {'pass' if r['judge'] else 'fail'}",
            f"  - Reply: {r['reply'][:300]}",
            f"  - Judge reasoning: {r['reason'][:400]}",
            "",
        ]
    if not dis:
        lines.append("None.")
    out = REPORTS_DIR / "calibration.md"
    out.write_text("\n".join(lines) + "\n")
    console.print(f"[green]Report:[/green] {out.relative_to(REPORTS_DIR.parent)}")
    return str(out)
