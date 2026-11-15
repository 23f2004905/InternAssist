import pytest
from uuid import uuid4

import services.vectorstore as vectorstore


@pytest.fixture
def fake_embeddings(monkeypatch):
    def mock_embed(texts, task_type):
        return [
            [0.1] * vectorstore.EMBEDDING_DIMENSIONS
            for _ in texts
        ]

    monkeypatch.setattr(vectorstore, "_embed_texts", mock_embed)


def test_add_and_delete_document_chunks(fake_embeddings):
    document_id = f"test-{uuid4()}"

    chunks = [
        {"text": "InternAssist test document content", "page_number": 1},
        {"text": "Another test document paragraph", "page_number": 2},
    ]

    inserted = vectorstore.add_chunks(chunks, document_id)
    assert inserted == 2

    stored = vectorstore.collection.get(
        where={"document_id": document_id}
    )
    assert len(stored["ids"]) == 2

    vectorstore.delete_document_chunks(document_id)

    remaining = vectorstore.collection.get(
        where={"document_id": document_id}
    )
    assert len(remaining["ids"]) == 0


def test_search_uses_query_embeddings(fake_embeddings):
    document_id = f"test-{uuid4()}"

    vectorstore.add_chunks(
        [{"text": "Internship placement information", "page_number": 1}],
        document_id,
    )

    results = vectorstore.search("Tell me about internships")

    assert len(results) >= 1
    assert results[0]["document_id"] == document_id
    assert results[0]["page_number"] == 1

    vectorstore.delete_document_chunks(document_id)


def test_search_raises_when_chroma_is_unavailable(monkeypatch):
    def fail():
        raise OSError("disk unavailable")

    monkeypatch.setattr(vectorstore, "_get_collection", fail)

    with pytest.raises(vectorstore.VectorStoreUnavailable):
        vectorstore.search("test query")
