
import logging
import os
from uuid import uuid4

import chromadb

logger = logging.getLogger(__name__)

_configured_path = os.getenv("CHROMA_DB_PATH")
if not _configured_path or not _configured_path.strip():
    CHROMA_DB_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db"
    )
elif not os.path.isabs(_configured_path):
    CHROMA_DB_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), _configured_path
    )
else:
    CHROMA_DB_PATH = _configured_path

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

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []

        retrieved_chunks = []

        for text, metadata, distance in zip(documents, metadatas, distances):
            metadata = metadata or {}
            retrieved_chunks.append({
                "text": text,
                "document_id": metadata.get("document_id"),
                "page_number": metadata.get("page_number"),
                "distance": distance
            })

        return retrieved_chunks

    except Exception as exc:
        logger.warning("ChromaDB search failed: %s", type(exc).__name__)
        return []

def delete_document_chunks(document_id):
    """Delete all chunks belonging to a document from ChromaDB."""
    try:
        collection.delete(
            where={"document_id": document_id}
        )
    except Exception as exc:
        logger.warning(
            "Failed to delete chunks for document %s from ChromaDB: %s",
            document_id,
            type(exc).__name__
        )
        raise
