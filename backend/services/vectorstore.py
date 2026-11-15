import os
from uuid import uuid4

import chromadb

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        path = os.getenv("CHROMA_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
        _client = chromadb.PersistentClient(path=os.path.abspath(path))
        _collection = _client.get_or_create_collection(name="documents")
    return _collection


def add_chunks(chunks, document_id):
    ids = [str(uuid4()) for _ in chunks]

    documents = [chunk["text"] for chunk in chunks]

    metadatas = []
    for chunk in chunks:
        metadata = {"document_id": document_id}
        if chunk.get("page_number") is not None:
            metadata["page_number"] = chunk["page_number"]
        metadatas.append(metadata)

    _get_collection().add(
        documents=documents,
        ids=ids,
        metadatas=metadatas
    )


def search(query, n_results=8):
    collection = _get_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    retrieved_chunks = []

    for i, document in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]

        retrieved_chunks.append({
            "text": document,
            "document_id": metadata.get("document_id"),
            "page_number": metadata.get("page_number")
        })

    return retrieved_chunks


def get_document_chunks(document_id):
    results = _get_collection().get(where={"document_id": document_id}, include=["documents", "metadatas"])
    return [
        {"id": chunk_id, "text": text, "metadata": metadata}
        for chunk_id, text, metadata in zip(
            results.get("ids", []), results.get("documents", []), results.get("metadatas", [])
        )
    ]


def delete_document_chunks(document_id):
    collection = _get_collection()
    collection.delete(where={"document_id": document_id})


def restore_document_chunks(chunks):
    if not chunks:
        return
    _get_collection().add(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
