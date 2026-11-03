import os
from uuid import uuid4
import chromadb

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "chroma_db")
os.makedirs(CHROMA_DB_PATH, exist_ok=True)

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection(name="documents")


def add_chunks(chunks, document_id):
    """Add text chunks with document metadata to ChromaDB collection."""
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
    """Search for relevant document chunks matching the query."""
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )

    if not results.get("documents") or not results["documents"][0]:
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


def delete_document_chunks(document_id):
    """Delete all chunks belonging to a document from ChromaDB."""
    collection.delete(
        where={"document_id": document_id}
    )
