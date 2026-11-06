
import os
from uuid import uuid4

import chromadb

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "chroma_db")

os.makedirs(CHROMA_DB_PATH, exist_ok=True)

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

collection = client.get_or_create_collection(name="documents")


def add_chunks(chunks, document_id):
    """Add text chunks with document metadata to ChromaDB."""

    if not chunks:
        return

    ids = [str(uuid4()) for _ in chunks]
    documents = [chunk["text"] for chunk in chunks]

    metadatas = [
        {
            "document_id": document_id,
            "page_number": chunk["page_number"]
        }
        for chunk in chunks
    ]

    collection.add(
        documents=documents,
        ids=ids,
        metadatas=metadatas
    )


def search(query, n_results=8):
    """Retrieve the most relevant chunks across all documents."""
    if not query or not query.strip():
        return []

    document_count = collection.count()

    if document_count == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, document_count),
        include=["documents", "metadatas", "distances"]
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved_chunks = []

    for text, metadata, distance in zip(documents, metadatas, distances):
        retrieved_chunks.append({
            "text": text,
            "document_id": metadata.get("document_id"),
            "page_number": metadata.get("page_number"),
            "distance": distance
        })

    return retrieved_chunks

def delete_document_chunks(document_id):
    """Delete all chunks belonging to a document from ChromaDB."""

    collection.delete(
        where={"document_id": document_id}
    )
