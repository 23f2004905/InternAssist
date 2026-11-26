
import chromadb
from uuid import uuid4

client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(name="documents")


def add_chunks(chunks, document_id):
    ids = [str(uuid4()) for _ in chunks]

    documents = [chunk["text"] for chunk in chunks]

    metadatas = []

    for chunk in chunks:
        metadata = {
            "document_id": document_id
        }

        # Store location information only when available
        for key, value in chunk.items():
            if key not in ["text", "document_id"] and value is not None:
                metadata[key] = value

        metadatas.append(metadata)

    collection.add(
        documents=documents,
        ids=ids,
        metadatas=metadatas
    )


def search(query, n_results=8):
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    retrieved_chunks = []

    for i, document in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]

        retrieved_chunk = {
            "text": document,
            "document_id": metadata.get("document_id")
        }

        # Return all available location metadata
        for key, value in metadata.items():
            if key != "document_id":
                retrieved_chunk[key] = value

        retrieved_chunks.append(retrieved_chunk)

    return retrieved_chunks
def delete_document_chunks(document_id):
    collection.delete(
        where={"document_id": document_id}
    )