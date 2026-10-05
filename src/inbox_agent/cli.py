"""`rei` command-line interface (contracts/cli.md)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .config import DATA_DIR, ConfigError, exit_on_config_error

app = typer.Typer(
    help="Harborview Realty inbox agent", no_args_is_help=True, pretty_exceptions_enable=False
)
console = Console()
EMAILS_DIR = DATA_DIR / "emails"


def _load_email(ref: str):
    from .schemas import Email

    path = Path(ref)
    if not path.exists():
        path = EMAILS_DIR / f"{ref.removesuffix('.json')}.json"
    if not path.exists():
        console.print(f"[red]Email not found:[/red] {ref}. Run `rei samples` to list samples.")
        raise typer.Exit(1)
    return Email(**json.loads(path.read_text()))


def _short(text: str, n: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _print_event(node: str, update) -> None:
    if not isinstance(update, dict):
        return
    for msg in update.get("messages", []) or []:
        kind = type(msg).__name__
        if kind == "AIMessage":
            for tc in msg.tool_calls:
                if tc["name"] == "Outcome":
                    continue
                args = ", ".join(f"{k}={v!r}" for k, v in tc["args"].items())
                console.print(f"[cyan]→ {tc['name']}[/cyan]({_short(args, 120)})")
        elif kind == "ToolMessage" and msg.name != "Outcome":
            style = "red" if str(msg.content).startswith("ERROR") else "dim"
            console.print(f"  [{style}]← {_short(msg.content)}[/{style}]")


def _coordinator_prompt(request: dict) -> dict:
    from .store import get_store

    args = request.get("args", {})
    store = get_store()
    listing = store.get_listing(args.get("listing_id", "")) or {}
    slot = store.slots.get(args.get("slot_id", ""))
    body = (
        f"[bold]Listing:[/bold] {args.get('listing_id')} — {listing.get('address', '?')}\n"
        f"[bold]Slot:[/bold] {args.get('slot_id')} — {slot.start if slot else '?'}\n"
        f"[bold]Buyer:[/bold] {args.get('contact_email')}"
    )
    console.print(
        Panel(body, title="Showing booking needs coordinator approval", border_style="yellow")
    )
    choice = Prompt.ask("[a]pprove / [e]dit / [r]eject", choices=["a", "e", "r"], default="a")
    if choice == "a":
        return {"type": "approve"}
    if choice == "r":
        reason = Prompt.ask("Reason", default="Coordinator rejected this booking.")
        return {"type": "reject", "message": reason}
    open_slots = store.open_slots(args.get("listing_id", ""))
    for s in open_slots:
        console.print(f"  {s['slot_id']}  {s['start']}")
    new_slot = Prompt.ask("New slot_id", choices=[s["slot_id"] for s in open_slots] or None)
    return {
        "type": "edit",
        "edited_action": {"name": request["name"], "args": {**args, "slot_id": new_slot}},
    }


def _print_outcome(result) -> None:
    if result.outcome is None:
        console.print(
            Panel(
                f"status: {result.status}\n{result.error or ''}",
                title="No outcome",
                border_style="red",
            )
        )
        return
    o = result.outcome
    cites = ", ".join(o["citations"]) or "—"
    lines = [o["message_to_sender"], "", f"[dim]citations: {cites}[/dim]"]
    if o.get("escalation"):
        e = o["escalation"]
        lines.append(f"[dim]escalation: {e['reason_category']} — {e['internal_note']}[/dim]")
    if result.booking:
        lines.append(f"[dim]booking: {result.booking}[/dim]")
    console.print(Panel("\n".join(lines), title=f"Outcome: {o['outcome']}", border_style="green"))
    console.print(
        f"[dim]{result.latency_s}s · tokens in/out {result.usage['input_tokens']}/"
        f"{result.usage['output_tokens']}[/dim]"
    )


@app.command()
def samples() -> None:
    """List sample emails in data/emails/."""
    table = Table("id", "from", "subject")
    for path in sorted(EMAILS_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        table.add_row(path.stem, d["from_address"], d.get("subject", ""))
    console.print(table)


@app.command()
def run(
    email: Annotated[str, typer.Argument(help="Path to an email JSON file or a sample id")],
    model: Annotated[str, typer.Option(help="claude | glm")] = os.environ.get("AGENT_MODEL", "glm"),
    auto_approve: Annotated[bool, typer.Option("--auto-approve")] = False,
    auto_reject: Annotated[bool, typer.Option("--auto-reject")] = False,
    fault: Annotated[
        str | None, typer.Option(help='Fault plan JSON, e.g. {"get_listing":["timeout"]}')
    ] = None,
    no_trace: Annotated[bool, typer.Option("--no-trace")] = False,
) -> None:
    """Process one email, streaming progress and prompting the coordinator on bookings."""
    if no_trace:
        os.environ["LANGSMITH_TRACING"] = "false"
    try:
        from .agent import run_email

        msg = _load_email(email)
        console.print(
            Panel(
                f"From: {msg.from_address}\nSubject: {msg.subject}\n\n{msg.body}",
                title=f"Inbound email {msg.email_id}",
                border_style="blue",
            )
        )
        policy = "approve" if auto_approve else "reject" if auto_reject else None
        result = run_email(
            msg,
            model_name=model,  # type: ignore[arg-type]
            fault_plan=json.loads(fault) if fault else None,
            approval_policy=policy,
            on_interrupt=None if policy else _coordinator_prompt,
            on_event=_print_event,
            variant="cli",
        )
    except ConfigError as e:
        exit_on_config_error(e)
    _print_outcome(result)
    if result.status == "completed":
        raise typer.Exit(0)
    raise typer.Exit(2 if result.status in ("no_outcome", "step_limit") else 1)


@app.command("eval")
def eval_(
    model: Annotated[str, typer.Option(help="claude | glm")] = "glm",
    variant: Annotated[str, typer.Option(help="experiment variant name")] = "baseline",
    reps: Annotated[int, typer.Option(help="repetitions per example")] = 3,
    split: Annotated[str, typer.Option(help="dev | heldout | all")] = "all",
    slice_: Annotated[str | None, typer.Option("--slice", help="only this slice")] = None,
    level: Annotated[str, typer.Option(help="all | retrieval | first-step | full")] = "all",
) -> None:
    """Run LangSmith experiments and write reports to reports/."""
    from .evals import run_eval

    try:
        names = run_eval.run(model, variant, reps, split, slice_, level)
    except ConfigError as e:
        exit_on_config_error(e)
    console.print("Experiments: " + ", ".join(names))


@app.command()
def draft(
    slice_: Annotated[str, typer.Option("--slice", help="dataset slice to draft for")],
    n: Annotated[int, typer.Option(help="number of drafts")] = 5,
) -> None:
    """Draft candidate emails for a slice into data/datasets/drafts/ (human review required)."""
    from .evals.draft import draft as run_draft

    for row in run_draft(slice_, n):
        console.print(Panel(row["body"], title=row["subject"], subtitle=row["why_tricky"]))


@app.command("setup-langsmith")
def setup_langsmith(
    datasets: Annotated[bool, typer.Option("--datasets")] = False,
    online: Annotated[bool, typer.Option("--online")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    force: Annotated[bool, typer.Option("--force", help="overwrite LangSmith edits")] = False,
) -> None:
    """Create/verify LangSmith datasets, queues, and the automation rule."""
    from .evals import langsmith_setup

    langsmith_setup.main(datasets=datasets, online=online, dry_run=dry_run, force=force)


@app.command("lint-dataset")
def lint_dataset(
    apply: Annotated[bool, typer.Option("--apply", help="apply mechanical fixes")] = False,
) -> None:
    """Check golden.jsonl for label mistakes; --apply writes the mechanical fixes."""
    from .evals import lint_dataset as L

    findings = L.lint()
    for f in findings:
        console.print(f"[bold]{f.id}[/bold] {f.kind:6} {f.code:20} {f.message}")
    if apply:
        console.print(f"Applied {L.apply_fixes(findings)} mechanical fix(es).")
    console.print(f"{len(findings)} finding(s).")


@app.command("pull-dataset")
def pull_dataset(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="show changes, write nothing")] = False,
) -> None:
    """Copy edits made in the LangSmith UI back into data/datasets/*.jsonl."""
    from .evals import langsmith_setup

    langsmith_setup.pull_datasets(dry_run=dry_run)


if __name__ == "__main__":
    app()
