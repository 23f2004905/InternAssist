import chromadb
from uuid import uuid4

client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(name="documents")


def add_chunks(chunks, document_id):
    ids = [str(uuid4()) for _ in chunks]
    metadatas = [{"document_id": document_id} for _ in chunks]

    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas
    )


def search(query, n_results=5):
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )

    if not results["documents"] or not results["documents"][0]:
        return ""

    return "\n\n".join(results["documents"][0])