"""Create and verify LangSmith objects. All names are prefixed `rei-` (shared workspace).

Datasets are versioned in git (`data/datasets/*.jsonl`); seeding upserts examples by their stable
id (`metadata.example_key`) so every edit becomes a new LangSmith dataset version, tagged with the
current git commit.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime

from rich.console import Console

from ..config import DATA_DIR

console = Console()
DATASETS = {
    "rei-golden": ("golden.jsonl", "Harborview inbox agent golden set (slices, expected outcomes)"),
    "rei-retrieval": ("retrieval.jsonl", "Retriever-only queries with expected KB doc ids"),
}


def _client():
    from langsmith import Client

    return Client()


def check_connection() -> None:
    client = _client()
    project = os.environ.get("LANGSMITH_PROJECT", "Focused")
    datasets = [d.name for d in client.list_datasets(dataset_name_contains="rei-")]
    console.print(
        f"LangSmith OK · project [bold]{project}[/bold] · rei datasets: "
        f"{', '.join(datasets) or 'none yet'}"
    )


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "nogit"


def _rows(filename: str) -> list[dict]:
    path = DATA_DIR / "datasets" / filename
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _comparable(metadata: dict | None) -> dict:
    """LangSmith adds `dataset_split` to metadata; ignore it when diffing."""
    return {k: v for k, v in (metadata or {}).items() if k != "dataset_split"}


def seed_dataset(name: str, filename: str, description: str) -> None:
    client = _client()
    if client.has_dataset(dataset_name=name):
        dataset = client.read_dataset(dataset_name=name)
    else:
        dataset = client.create_dataset(name, description=description)
    existing = {
        (e.metadata or {}).get("example_key"): e
        for e in client.list_examples(dataset_id=dataset.id)
    }
    rows = _rows(filename)
    created = updated = 0
    to_create = []
    for row in rows:
        key = row["id"]
        metadata = {**row.get("metadata", {}), "example_key": key, "split": row.get("split")}
        split = row.get("split") or "base"
        current = existing.pop(key, None)
        if current is None:
            to_create.append(
                {
                    "inputs": row["inputs"],
                    "outputs": row["outputs"],
                    "metadata": metadata,
                    "split": split,
                }
            )
        elif (
            current.inputs != row["inputs"]
            or current.outputs != row["outputs"]
            or _comparable(current.metadata) != metadata
        ):
            client.update_example(
                current.id,
                inputs=row["inputs"],
                outputs=row["outputs"],
                metadata=metadata,
                split=split,
            )
            updated += 1
    if to_create:
        client.create_examples(dataset_id=dataset.id, examples=to_create)
        created = len(to_create)
    removed = len(existing)
    if existing:
        client.delete_examples([e.id for e in existing.values()])
    tag = _git_sha()
    if created or updated or removed:
        client.update_dataset_tag(dataset_name=name, as_of=datetime.now(UTC), tag=tag)
    console.print(
        f"[green]{name}[/green]: {len(rows)} examples · +{created} ~{updated} "
        f"-{removed} · tag {tag}"
    )


def seed_datasets() -> None:
    for name, (filename, description) in DATASETS.items():
        seed_dataset(name, filename, description)


def main(datasets: bool = False, online: bool = False, dry_run: bool = False) -> None:
    if dry_run or not (datasets or online):
        check_connection()
        return
    if datasets:
        seed_datasets()
    if online:
        from .monitor import setup_online

        setup_online()
