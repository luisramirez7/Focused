"""Create and verify LangSmith objects. All names are prefixed `rei-` (shared workspace)."""

from __future__ import annotations

import os

from rich.console import Console

console = Console()


def check_connection() -> None:
    from langsmith import Client

    client = Client()
    project = os.environ.get("LANGSMITH_PROJECT", "Focused")
    datasets = [d.name for d in client.list_datasets(dataset_name_contains="rei-")]
    console.print(
        f"LangSmith OK · project [bold]{project}[/bold] · rei datasets: "
        f"{', '.join(datasets) or 'none yet'}"
    )


def main(datasets: bool = False, online: bool = False, dry_run: bool = False) -> None:
    if dry_run or not (datasets or online):
        check_connection()
        return
    if datasets:
        raise NotImplementedError("seed_datasets arrives with the evaluation phase (T042)")
    if online:
        raise NotImplementedError("setup_online arrives with the monitoring phase (T066)")
