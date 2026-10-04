"""Retrieval over the brokerage knowledge base (RAG step).

Docs are short markdown files; each `##` section becomes one chunk with id
`{doc_id}#{section-slug}`. Chunks are embedded once per process into an in-memory vector store.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from .config import DATA_DIR, make_embeddings

KB_DIR = DATA_DIR / "kb"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse(path: Path) -> tuple[dict, str]:
    raw = path.read_text()
    meta: dict = {}
    if raw.startswith("---"):
        _, front, raw = raw.split("---", 2)
        for line in front.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, raw.strip()


def load_chunks(kb_dir: Path = KB_DIR) -> list[Document]:
    chunks: list[Document] = []
    for path in sorted(kb_dir.glob("*.md")):
        doc_id = path.stem
        meta, body = _parse(path)
        title = meta.get("title", doc_id)
        sections = re.split(r"^## +", body, flags=re.MULTILINE)
        for section in sections[1:]:
            heading, _, text = section.partition("\n")
            chunks.append(
                Document(
                    page_content=f"{title} — {heading.strip()}\n{text.strip()}",
                    metadata={
                        "doc_id": doc_id,
                        "chunk_id": f"{doc_id}#{_slug(heading)}",
                        "title": title,
                        "category": meta.get("category", ""),
                    },
                )
            )
    return chunks


class KnowledgeBase:
    def __init__(self, embeddings: Embeddings, kb_dir: Path = KB_DIR):
        self.chunks = load_chunks(kb_dir)
        self.store = InMemoryVectorStore.from_documents(self.chunks, embeddings)

    def search(self, query: str, k: int = 4) -> list[dict]:
        docs = self.store.similarity_search(query, k=k)
        return [
            {
                "doc_id": d.metadata["doc_id"],
                "chunk_id": d.metadata["chunk_id"],
                "title": d.metadata["title"],
                "text": d.page_content,
            }
            for d in docs
        ]


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    return KnowledgeBase(make_embeddings())


def search(query: str, k: int = 4) -> list[dict]:
    return get_kb().search(query, k=k)
