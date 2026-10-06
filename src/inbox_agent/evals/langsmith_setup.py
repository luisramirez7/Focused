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


def _differs(remote, row: dict) -> bool:
    metadata = {**row.get("metadata", {}), "example_key": row["id"], "split": row.get("split")}
    return (
        remote.inputs != row["inputs"]
        or remote.outputs != row["outputs"]
        or _comparable(remote.metadata) != metadata
    )


def remote_drift(name: str, filename: str) -> list[str]:
    """Examples whose LangSmith version differs from the file, or that exist only in LangSmith
    (e.g. edited or added in the UI). Seeding would overwrite or delete these."""
    client = _client()
    if not client.has_dataset(dataset_name=name):
        return []
    rows = {r["id"]: r for r in _rows(filename)}
    drift = []
    for e in client.list_examples(dataset_name=name):
        key = (e.metadata or {}).get("example_key")
        if key not in rows:
            drift.append(f"{key or e.id} (only in LangSmith)")
        elif _differs(e, rows[key]):
            drift.append(key)
    return sorted(drift)


def pull_dataset(name: str, filename: str, dry_run: bool = False) -> list[str]:
    """Copy LangSmith edits back into the git file (LangSmith wins for examples it has; examples
    that exist only in the file are kept; examples added in the UI get new ids)."""
    client = _client()
    path = DATA_DIR / "datasets" / filename
    rows = _rows(filename)
    by_id = {r["id"]: i for i, r in enumerate(rows)}
    prefix = rows[0]["id"].split("-")[0] if rows else "G"
    next_n = max((int(r["id"].split("-")[1]) for r in rows), default=0) + 1
    changed = []
    for e in client.list_examples(dataset_name=name):
        meta = _comparable(e.metadata)
        key = meta.pop("example_key", None)
        split = meta.pop("split", None) or ((e.metadata or {}).get("dataset_split") or [None])[0]
        if key is None or key not in by_id:
            if key is None:
                key = f"{prefix}-{next_n:03d}"
                next_n += 1
            rows.append(
                {
                    "inputs": e.inputs,
                    "outputs": e.outputs,
                    "metadata": meta,
                    "id": key,
                    "split": split,
                }
            )
            by_id[key] = len(rows) - 1
            changed.append(f"{key} (new from LangSmith)")
            continue
        row = rows[by_id[key]]
        new = {"inputs": e.inputs, "outputs": e.outputs, "metadata": meta, "id": key}
        if "split" in row or split not in (None, "base"):
            new["split"] = split
        if new != row:
            rows[by_id[key]] = new
            changed.append(key)
    if changed and not dry_run:
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    verb = "Would update" if dry_run else "Updated"
    console.print(
        f"[green]{name}[/green] → {filename}: {verb} {len(changed)} example(s)"
        + (f": {', '.join(changed)}" if changed else "")
    )
    return changed


def seed_dataset(name: str, filename: str, description: str, force: bool = False) -> None:
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
    drift = [] if force else remote_drift(name, filename)
    if drift:
        console.print(
            f"[red]Refusing to seed {name}:[/red] {len(drift)} example(s) in LangSmith differ "
            f"from {filename} (edited in the UI?): {', '.join(drift[:12])}"
            f"{' …' if len(drift) > 12 else ''}\n"
            "Run `rei pull-dataset` to copy those edits into the file first, "
            "or `rei setup-langsmith --datasets --force` to overwrite them."
        )
        raise SystemExit(1)
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


def seed_datasets(force: bool = False) -> None:
    for name, (filename, description) in DATASETS.items():
        seed_dataset(name, filename, description, force=force)


def pull_datasets(dry_run: bool = False) -> None:
    for name, (filename, _) in DATASETS.items():
        pull_dataset(name, filename, dry_run=dry_run)


def main(datasets: bool = False, dry_run: bool = False, force: bool = False) -> None:
    if dry_run or not datasets:
        check_connection()
        return
    seed_datasets(force=force)
