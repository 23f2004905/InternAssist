
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
    """Search each uploaded document and combine relevant results."""

    if not query or not query.strip():
        return []

    all_metadata = collection.get(include=["metadatas"])

    if not all_metadata["metadatas"]:
        return []

    document_ids = {
        metadata.get("document_id")
        for metadata in all_metadata["metadatas"]
        if metadata and metadata.get("document_id") is not None
    }

    retrieved_chunks = []

    for document_id in document_ids:

        document_data = collection.get(
            where={"document_id": document_id},
            include=["metadatas"]
        )

        document_count = len(document_data["ids"])

        if document_count == 0:
            continue

        results = collection.query(
            query_texts=[query],
            n_results=min(4, document_count),
            where={"document_id": document_id},
            include=["documents", "metadatas", "distances"]
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for text, metadata, distance in zip(
            documents, metadatas, distances
        ):
            retrieved_chunks.append({
                "text": text,
                "document_id": metadata.get("document_id"),
                "page_number": metadata.get("page_number"),
                "distance": distance
            })

    retrieved_chunks.sort(
        key=lambda chunk: chunk["distance"]
    )

    return retrieved_chunks[:n_results]


def delete_document_chunks(document_id):
    """Delete all chunks belonging to a document from ChromaDB."""

    collection.delete(
        where={"document_id": document_id}
    )
