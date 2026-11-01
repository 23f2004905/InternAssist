from uuid import uuid4

from services.vectorstore import (
    add_chunks,
    collection,
    delete_document_chunks,
)


def test_delete_document_chunks():
    document_id = f"test-{uuid4()}"

    chunks = [
        {"text": "InternAssist test document content", "page_number": 1},
        {"text": "Another test document paragraph", "page_number": 2},
    ]

    add_chunks(chunks, document_id)

    stored = collection.get(
        where={"document_id": document_id}
    )

    assert len(stored["ids"]) == 2

    delete_document_chunks(document_id)

    remaining = collection.get(
        where={"document_id": document_id}
    )

    assert len(remaining["ids"]) == 0
