from inbox_agent.retrieval import load_chunks


def test_chunks_have_section_ids():
    chunks = load_chunks()
    ids = {c.metadata["chunk_id"] for c in chunks}
    assert "showing-policy#who-can-tour" in ids
    assert len({c.metadata["doc_id"] for c in chunks}) == 15


def test_search_returns_k_results(fake_kb):
    results = fake_kb.search("Do I need a buyer agreement to tour?", k=4)
    assert len(results) == 4
    assert all({"doc_id", "chunk_id", "title", "text"} <= set(r) for r in results)
