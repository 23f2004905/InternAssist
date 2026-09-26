import chromadb
from uuid import uuid4

client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(name="documents")


def add_chunks(chunks, document_id):
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