import logging
import os
import threading
import time
from itertools import islice
from uuid import uuid4

logger = logging.getLogger("app.vectorstore")

_configured_path = os.getenv("CHROMA_DB_PATH")

if not _configured_path or not _configured_path.strip():
    CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    CHROMA_DB_PATH = os.path.abspath(CHROMA_DB_PATH)
elif not os.path.isabs(_configured_path):
    CHROMA_DB_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", _configured_path)
    )
else:
    CHROMA_DB_PATH = _configured_path

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
COLLECTION_NAME = "documents_gemini_001_768"
MAX_EMBEDDING_BATCH_SIZE = 16

_init_lock = threading.RLock()
_client = None
_collection = None
_owner_pid = None


class VectorStoreUnavailable(RuntimeError):
    """Raised when vector storage or retrieval is unavailable."""


def _embed_texts(texts, task_type):
    """Generate embeddings through the shared Gemini API client."""
    if not texts:
        return []

    from google.genai import types
    from services.llm import get_gemini_client

    gemini_client = get_gemini_client()

    if not gemini_client:
        raise VectorStoreUnavailable("Gemini embedding service is unavailable")

    response = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )

    embeddings = getattr(response, "embeddings", None)

    if not embeddings or len(embeddings) != len(texts):
        raise VectorStoreUnavailable("Gemini returned an invalid embedding response")

    vectors = []

    for embedding in embeddings:
        values = getattr(embedding, "values", None)

        if not values or len(values) != EMBEDDING_DIMENSIONS:
            raise VectorStoreUnavailable(
                "Gemini returned an unexpected embedding dimension"
            )

        vectors.append([float(value) for value in values])

    return vectors


def _get_collection():
    """Connect to Chroma lazily and protect against unsafe process forks."""
    global _client, _collection, _owner_pid

    pid = os.getpid()

    if _collection is not None:
        if _owner_pid != pid:
            raise RuntimeError("ChromaDB client was created before a process fork")
        return _collection

    with _init_lock:
        if _collection is not None:
            if _owner_pid != pid:
                raise RuntimeError("ChromaDB client was created before a process fork")
            return _collection

        import chromadb

        started = time.perf_counter()
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )

        _owner_pid = pid

        logger.info(
            "[VECTOR] Gemini ChromaDB collection ready in %.2fs "
            "(pid=%s, collection=%s)",
            time.perf_counter() - started,
            pid,
            COLLECTION_NAME,
        )

        return _collection


class _LazyCollection:
    """Drop-in collection proxy that connects on first use."""

    def __getattr__(self, name):
        return getattr(_get_collection(), name)


collection = _LazyCollection()


def add_chunks(chunks, document_id, batch_size=64):
    """Embed and insert document chunks in bounded batches."""
    target = _get_collection()
    batch_size = max(1, min(int(batch_size), MAX_EMBEDDING_BATCH_SIZE))

    iterator = iter(chunks)
    inserted = 0

    while True:
        batch = list(islice(iterator, batch_size))

        if not batch:
            break

        texts = [chunk["text"] for chunk in batch]

        embeddings = _embed_texts(
            texts,
            task_type="RETRIEVAL_DOCUMENT",
        )

        target.add(
            documents=texts,
            embeddings=embeddings,
            ids=[str(uuid4()) for _ in batch],
            metadatas=[
                {
                    "document_id": document_id,
                    "page_number": int(chunk["page_number"]),
                }
                for chunk in batch
            ],
        )

        inserted += len(batch)

    return inserted


def search(query, n_results=8):
    """Retrieve relevant chunks using Gemini query embeddings."""
    if not query or not query.strip():
        return []

    try:
        query_embedding = _embed_texts(
            [query],
            task_type="RETRIEVAL_QUERY",
        )[0]

        results = _get_collection().query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []

        retrieved_chunks = []

        for text, metadata, distance in zip(documents, metadatas, distances):
            metadata = metadata or {}

            retrieved_chunks.append(
                {
                    "text": text,
                    "document_id": metadata.get("document_id"),
                    "page_number": metadata.get("page_number"),
                    "distance": distance,
                }
            )

        return retrieved_chunks

    except Exception as exc:
        logger.exception("Vector search failed")
        raise VectorStoreUnavailable(
            "Vector retrieval is temporarily unavailable"
        ) from exc


def delete_document_chunks(document_id):
    """Delete all chunks belonging to a document."""
    try:
        _get_collection().delete(where={"document_id": document_id})
    except Exception as exc:
        logger.warning(
            "Failed to delete chunks for document %s: %s",
            document_id,
            type(exc).__name__,
        )
        raise


def indexed_document_ids(document_id=None):
    """Check whether a document has indexed chunks."""
    try:
        kwargs = {"include": []}

        if document_id is not None:
            kwargs["where"] = {"document_id": document_id}

        result = _get_collection().get(**kwargs)
        return bool(result.get("ids"))

    except Exception as exc:
        logger.exception("Could not inspect ChromaDB index")
        raise VectorStoreUnavailable(
            "Vector index inspection is unavailable"
        ) from exc
