"""Re-grade saved experiment results against the current golden labels (no agent re-runs).

Used for honest before/after: the baseline and every later variant are scored by the same code
against the same label version, so label fixes are never counted as agent improvements.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..config import DATA_DIR, REPORTS_DIR
from . import deterministic as D
from . import stats as S

HEADLINE = [
    "outcome_correct",
    "escalation_reason_correct",
    "facts_present",
    "forbidden_absent",
    "numeric_claims_grounded",
    "citations_valid",
    "required_citations_present",
    "no_forbidden_tool",
    "tools_expected_called",
    "order_invariants_ok",
    "no_repeated_calls",
    "no_unapproved_booking",
    "pii_absent_in_reply",
    "tool_call_count",
]
EVALUATORS = [f for f in D.FULL_RUN_EVALUATORS if f is not D.trajectory_match]


def _golden() -> dict[str, dict]:
    rows = [
        json.loads(x)
        for x in (DATA_DIR / "datasets/golden.jsonl").read_text().splitlines()
        if x.strip()
    ]
    return {r["inputs"]["email"]["email_id"]: r for r in rows}


def _call(fn, outputs, reference, inputs):
    import inspect

    params = inspect.signature(fn).parameters
    kwargs = {"outputs": outputs}
    if "reference_outputs" in params:
        kwargs["reference_outputs"] = reference
    if "inputs" in params:
        kwargs["inputs"] = inputs
    return fn(**kwargs)


def rescore(raw_path: Path) -> pd.DataFrame:
    """One row per run: example id, split, slices, outcome, and every metric (NaN = n/a)."""
    gold = _golden()
    rows = []
    for line in raw_path.read_text().splitlines():
        r = json.loads(line)
        email_id = (r.get("inputs.email") or {}).get("email_id")
        if email_id not in gold:
            continue  # example removed from the dataset since this run
        g = gold[email_id]
        outputs = {k.removeprefix("outputs."): v for k, v in r.items() if k.startswith("outputs.")}
        row = {
            "example": g["id"],
            "split": g.get("split"),
            "slices": g["metadata"]["slices"],
            "outcome": (outputs.get("outcome") or {}).get("outcome", "no_outcome"),
            "expected": g["outputs"]["expected_outcome"],
        }
        for fn in EVALUATORS:
            res = _call(fn, outputs, g["outputs"], g["inputs"])
            for item in res.get("results", [res]) if "results" in res else [res]:
                if "score" in item:
                    row[item["key"]] = item["score"]
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame, split: str = "all") -> dict[str, tuple[float, float, float]]:
    if split != "all":
        df = df[df["split"] == split]
    out = {}
    for m in HEADLINE:
        if m in df:
            means = df.dropna(subset=[m]).groupby("example")[m].mean()
            out[m] = (*S.bootstrap_ci(means.to_numpy()), len(means))
    primary_reply = df[df["expected"] == "reply"]
    out["escalated_when_reply_primary"] = (
        float((primary_reply["outcome"] == "escalate").mean())
        if len(primary_reply)
        else float("nan"),
        float("nan"),
        float("nan"),
        len(primary_reply),
    )
    return out


def compare(before: Path, after: Path, split: str = "dev") -> str:
    a, b = rescore(before), rescore(after)
    sa, sb = summarize(a, split), summarize(b, split)
    lines = [f"| Metric ({split}) | Before | After | Change (paired 95% CI) |", "|---|---|---|---|"]
    for m in [*HEADLINE, "escalated_when_reply_primary"]:
        if m not in sa or m not in sb:
            continue
        if m == "escalated_when_reply_primary":
            lines.append(
                f"| {m} | {sa[m][0]:.0%} of {sa[m][3]} runs | {sb[m][0]:.0%} of "
                f"{sb[m][3]} runs | — |"
            )
            continue
        da = a if split == "all" else a[a["split"] == split]
        db = b if split == "all" else b[b["split"] == split]
        ma = da.dropna(subset=[m]).groupby("example")[m].mean()
        mb = db.dropna(subset=[m]).groupby("example")[m].mean()
        delta = S.paired_bootstrap_delta(ma, mb)
        fmt = (lambda v: f"{v:.2f}") if m == "tool_call_count" else (lambda v: f"{v:.0%}")
        noise = " (within noise)" if S.within_noise(delta) else ""
        lines.append(
            f"| {m} | {fmt(sa[m][0])} | {fmt(sb[m][0])} | {delta[0]:+.2f} "
            f"[{delta[1]:+.2f}, {delta[2]:+.2f}]{noise} |"
        )
    return "\n".join(lines)


def latest_raw(prefix: str) -> Path:
    files = sorted((REPORTS_DIR / "raw").glob(f"{prefix}*.jsonl"), key=lambda p: p.stat().st_mtime)
    files = [f for f in files if "firststep" not in f.name]
    if not files:
        raise FileNotFoundError(f"No raw results matching {prefix}")
    return files[-1]
