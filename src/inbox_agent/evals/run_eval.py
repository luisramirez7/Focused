"""`rei eval`: run named LangSmith experiments and write a markdown report per experiment."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime

import pandas as pd
from rich.console import Console

from .. import __version__
from ..config import REPORTS_DIR, settings
from ..prompts import PROMPT_VERSION
from . import deterministic as D
from . import stats as S
from .summary import CLASSES, SUMMARY_EVALUATORS, confusion
from .targets import first_step_target, full_run_target, retriever_target

console = Console()
GOLDEN = "rei-golden"
RETRIEVAL = "rei-retrieval"

HEADLINE = [
    "outcome_correct",
    "escalation_reason_correct",
    "facts_present",
    "numeric_claims_grounded",
    "forbidden_absent",
    "citations_valid",
    "no_forbidden_tool",
    "no_unapproved_booking",
    "pii_absent_in_reply",
    "pii_absent_in_model_input",
    "has_outcome",
    "tools_expected_called",
    "tool_args_correct",
    "trajectory_match",
    "order_invariants_ok",
    "no_repeated_calls",
    "within_budgets",
    "tool_call_count",
]
SLICE_METRICS = ["outcome_correct", "forbidden_absent", "numeric_claims_grounded"]


def _client():
    from langsmith import Client

    return Client()


def load_examples(dataset: str, split: str = "all", slice_: str | None = None) -> list:
    client = _client()
    kwargs = {"dataset_name": dataset}
    if split != "all":
        kwargs["splits"] = [split]
    examples = list(client.list_examples(**kwargs))
    if slice_:
        examples = [e for e in examples if slice_ in (e.metadata or {}).get("slices", [])]
    return examples


def _evaluate(target, data, evaluators, prefix, reps, metadata, summary=()):
    from langsmith import evaluate

    return evaluate(
        target,
        data=data,
        evaluators=evaluators,
        summary_evaluators=list(summary),
        experiment_prefix=prefix,
        num_repetitions=reps,
        max_concurrency=int(os.environ.get("REI_EVAL_CONCURRENCY", "4")),
        metadata=metadata,
        # Evaluator calls are not traced (scores still attach as feedback). Tracing them created
        # ~20 extra traces per run and exhausted the workspace's monthly trace limit.
        disable_evaluator_tracing=True,
    )


# Rough per-email cost (USD) from the baseline; used only for the pre-run budget check.
EST_COST_PER_RUN = {"claude": 0.03, "glm": 0.007}
MAX_RUNS = int(os.environ.get("REI_EVAL_MAX_RUNS", "250"))
MAX_COST = float(os.environ.get("REI_EVAL_MAX_COST", "8"))


class BudgetExceeded(RuntimeError):
    pass


def budget_check(model: str, n_full: int, n_first: int, reps: int, confirmed: bool) -> str:
    runs = (n_full + n_first) * reps
    cost = n_full * reps * EST_COST_PER_RUN.get(model, 0.03)
    summary = (
        f"{model}: {n_full} full + {n_first} first-step examples x {reps} reps = {runs} "
        f"runs, est. ${cost:.2f}"
    )
    if (runs > MAX_RUNS or cost > MAX_COST) and not confirmed:
        raise BudgetExceeded(
            f"{summary} exceeds the cap ({MAX_RUNS} runs / ${MAX_COST:.0f}). "
            "Narrow with --split/--slice/--reps, or pass --yes."
        )
    return summary


def run(
    model: str,
    variant: str,
    reps: int = 1,
    split: str = "all",
    slice_: str | None = None,
    level: str = "all",
    extra_evaluators: list | None = None,
    confirmed: bool = False,
) -> list[str]:
    metadata = {
        "model": model,
        "variant": variant,
        "prompt_version": PROMPT_VERSION,
        "agent_version": __version__,
        "judge_model": settings().judge_model,
        "split": split,
        "slice": slice_ or "all",
    }
    experiments = []
    golden = load_examples(GOLDEN, split, slice_) if level != "retrieval" else []
    # Level 2 only scores examples that name an acceptable first tool.
    first_step = [e for e in golden if (e.outputs or {}).get("expected_first_tool")]
    n_full = len(golden) if level in ("all", "full") else 0
    n_first = len(first_step) if level in ("all", "first-step") else 0
    if level != "retrieval":
        console.print(
            "[bold]Budget:[/bold] " + budget_check(model, n_full, n_first, reps, confirmed)
        )
    # The retriever does not depend on the agent model: run it only when asked for explicitly.
    if level == "retrieval":
        res = _evaluate(
            retriever_target(),
            load_examples(RETRIEVAL),
            D.RETRIEVAL_EVALUATORS,
            f"rei-{variant}-retrieval",
            1,
            {**metadata, "level": "retrieval"},
        )
        experiments.append(write_report(res, "retrieval", metadata))
    if level in ("all", "first-step") and first_step:
        res = _evaluate(
            first_step_target(model, variant),
            first_step,
            D.FIRST_STEP_EVALUATORS,
            f"rei-{variant}-{model}-firststep",
            reps,
            {**metadata, "level": "first-step"},
        )
        experiments.append(write_report(res, "first-step", metadata))
    if level in ("all", "full"):
        evaluators = D.FULL_RUN_EVALUATORS + list(extra_evaluators or [])
        res = _evaluate(
            full_run_target(model, variant),
            golden,
            evaluators,
            f"rei-{variant}-{model}",
            reps,
            {**metadata, "level": "full"},
            SUMMARY_EVALUATORS,
        )
        experiments.append(write_report(res, "full", metadata, golden))
    return experiments


# --- reporting ---------------------------------------------------------------------------------


def _fmt(ci: tuple[float, float, float], pct: bool = True) -> str:
    mean, lo, hi = ci
    if math.isnan(mean):
        return "—"
    if pct:
        return f"{mean:.0%} [{lo:.0%}, {hi:.0%}]"
    return f"{mean:.1f} [{lo:.1f}, {hi:.1f}]"


def results_frame(res, examples: list | None = None) -> pd.DataFrame:
    df = res.to_pandas()
    if examples:
        meta = pd.DataFrame(
            [
                {
                    "example_id": str(e.id),
                    "slices": (e.metadata or {}).get("slices", []),
                    "split": (e.metadata or {}).get("split"),
                }
                for e in examples
            ]
        )
        df["example_id"] = df["example_id"].astype(str)
        df = df.merge(meta, on="example_id", how="left")
    return df


# USD per million tokens (input, output) — research R5; used only when LangSmith has no cost.
PRICES = {"claude": (2.0, 10.0), "glm": (1.40, 4.40)}


def local_cost(df: pd.DataFrame) -> float | None:
    model = str(df.get("model", pd.Series(["glm"])).iloc[0]) if "model" in df else None
    usage = df["outputs.usage"].dropna()
    if usage.empty or model not in PRICES:
        return None
    pin, pout = PRICES[model]
    tokens_in = sum(u.get("input_tokens", 0) for u in usage)
    tokens_out = sum(u.get("output_tokens", 0) for u in usage)
    return (tokens_in * pin + tokens_out * pout) / 1e6


def experiment_stats(name: str, df: pd.DataFrame) -> dict:
    out = {"total_cost": None, "latency_p50": None, "latency_p95": None, "runs": len(df)}
    try:
        project = _client().read_project(project_name=name, include_stats=True)
        out["total_cost"] = float(project.total_cost) if project.total_cost is not None else None
    except Exception as e:  # stats are best-effort; never fail the report
        console.print(f"[yellow]Could not read project stats: {e}[/yellow]")
    if not out["total_cost"] and "outputs.usage" in df:
        out["total_cost"] = local_cost(df)
        out["cost_source"] = "computed from token usage (LangSmith had no cost data)"
    if "execution_time" in df:
        out["latency_p50"] = S.percentile(df["execution_time"].dropna(), 50)
        out["latency_p95"] = S.percentile(df["execution_time"].dropna(), 95)
    return out


def write_report(res, level: str, metadata: dict, examples: list | None = None) -> str:
    name = res.experiment_name
    df = results_frame(res, examples)
    df["model"] = metadata["model"]
    raw = REPORTS_DIR / "raw" / f"{name}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(raw, orient="records", lines=True, default_handler=str)
    stats = experiment_stats(name, df)
    model = (
        settings().fireworks_embedding_model.split("/")[-1]
        if level == "retrieval"
        else (metadata["model"])
    )
    lines = [
        f"# Experiment `{name}`",
        "",
        f"- Level: **{level}** · model: **{model}** · variant: "
        f"**{metadata['variant']}** · prompt {metadata['prompt_version']} · "
        f"generated {datetime.now():%Y-%m-%d %H:%M}",
        f"- Runs: {stats['runs']} · examples: {df['example_id'].nunique()}",
    ]
    if stats["total_cost"] is not None and df["example_id"].nunique():
        lines.append(
            f"- Cost: ${stats['total_cost']:.3f} total · "
            f"${stats['total_cost'] / stats['runs']:.4f} per email"
        )
    if stats["latency_p50"] is not None:
        lines.append(
            f"- Latency: p50 {stats['latency_p50']:.1f}s · p95 {stats['latency_p95']:.1f}s"
        )
    lines += [
        "",
        "Scores are per-example means over repetitions, with 95% bootstrap CIs over examples.",
        "",
        "| Metric | Score | n |",
        "|---|---|---|",
    ]
    for col in sorted(c for c in df.columns if c.startswith("feedback.")):
        key = col.removeprefix("feedback.")
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        means = S.per_example_means(df, col)
        pct = key != "tool_call_count"
        lines.append(f"| {key} | {_fmt(S.bootstrap_ci(means.to_numpy()), pct)} | {len(means)} |")
    if level == "full" and examples:
        lines += _slice_section(df) + _confusion_section(df)
    path = REPORTS_DIR / f"{name}.md"
    path.write_text("\n".join(lines) + "\n")
    console.print(f"[green]Report:[/green] {path.relative_to(REPORTS_DIR.parent)}")
    return name


def _slice_section(df: pd.DataFrame) -> list[str]:
    lines = ["", "## By slice (directional — small n per slice)", ""]
    header = "| Slice | n | " + " | ".join(SLICE_METRICS) + " |"
    lines += [header, "|" + "---|" * (len(SLICE_METRICS) + 2)]
    tables = {
        m: S.slice_table(df, f"feedback.{m}").set_index("slice")
        for m in SLICE_METRICS
        if f"feedback.{m}" in df
    }
    slices = sorted(set().union(*[t.index for t in tables.values()])) if tables else []
    for s in slices:
        cells, n = [], 0
        for m in SLICE_METRICS:
            t = tables.get(m)
            if t is not None and s in t.index:
                row = t.loc[s]
                n = max(n, int(row["n"]))
                cells.append(_fmt((row["mean"], row["ci_low"], row["ci_high"])))
            else:
                cells.append("—")
        lines.append(f"| {s} | {n} | " + " | ".join(cells) + " |")
    return lines


def _confusion_section(df: pd.DataFrame) -> list[str]:
    outs = [
        {"outcome": o} if isinstance(o, dict) else {"outcome": None}
        for o in df.get("outputs.outcome", [])
    ]
    refs = [
        {"expected_outcome": e, "acceptable_outcomes": a}
        for e, a in zip(
            df["reference.expected_outcome"], df["reference.acceptable_outcomes"], strict=True
        )
    ]
    m = confusion(outs, refs)
    lines = [
        "",
        "## Outcome confusion matrix, lenient (an acceptable alternative counts as correct)",
        "",
        "| expected \\ predicted | " + " | ".join(CLASSES) + " |",
        "|" + "---|" * (len(CLASSES) + 1),
    ]
    for e in CLASSES:
        if sum(m[e].values()):
            lines.append(f"| {e} | " + " | ".join(str(m[e][p]) for p in CLASSES) + " |")
    strict = confusion(
        outs,
        [
            {
                "expected_outcome": r["expected_outcome"],
                "acceptable_outcomes": [r["expected_outcome"]],
            }
            for r in refs
        ],
    )
    lines += [
        "",
        "## Strict confusion matrix (vs the single expected_outcome)",
        "",
        "Shows the agent's tendencies (e.g. escalating where a reply was the primary label) "
        "even when the alternative was acceptable.",
        "",
        "| expected \\ predicted | " + " | ".join(CLASSES) + " |",
        "|" + "---|" * (len(CLASSES) + 1),
    ]
    for e in CLASSES:
        if sum(strict[e].values()):
            lines.append(f"| {e} | " + " | ".join(str(strict[e][p]) for p in CLASSES) + " |")
    lines += ["", "<!-- raw: " + json.dumps({"lenient": m, "strict": strict}) + " -->"]
    return lines
