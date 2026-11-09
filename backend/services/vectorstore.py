
import logging
import os
import threading
import time
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

_init_lock = threading.RLock()
_client = None
_collection = None
_owner_pid = None


def _get_collection():
    """Return this process's Chroma collection, connecting on first use.

    Connecting lazily keeps ChromaDB out of worker boot. Nothing is
    initialised in a process that may later fork. ChromaDB's Rust runtime
    is not fork-safe, so a child inheriting an initialised client must fail
    fast rather than risk hanging inside collection calls.
    """
    global _client, _collection, _owner_pid

    pid = os.getpid()

    if _collection is not None:
        if _owner_pid != pid:
            logger.error(
                "[VECTOR] ChromaDB was initialised in pid %s but is being used "
                "from pid %s (forked after init); refusing to call it because it "
                "would hang.",
                _owner_pid,
                pid,
            )
            raise RuntimeError(
                "ChromaDB client was created before a process fork"
            )
        return _collection

    with _init_lock:
        if _collection is not None:
            if _owner_pid != pid:
                logger.error(
                    "[VECTOR] ChromaDB client belongs to pid %s, current pid is %s",
                    _owner_pid,
                    pid,
                )
                raise RuntimeError(
                    "ChromaDB client was created before a process fork"
                )
            return _collection

        import chromadb

        started = time.perf_counter()
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)

        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_or_create_collection(name="documents")
        _owner_pid = pid

        logger.info(
            "[VECTOR] ChromaDB ready in %.2fs (pid=%s, path=%s)",
            time.perf_counter() - started,
            pid,
            CHROMA_DB_PATH,
        )

        return _collection


class _LazyCollection:
    """Drop-in stand-in for the collection that connects on first attribute use."""

    def __getattr__(self, name):
        return getattr(_get_collection(), name)


collection = _LazyCollection()


def add_chunks(chunks, document_id):
    """Add text chunks with document metadata to ChromaDB."""

    if not chunks:
        return

    ids = [str(uuid4()) for _ in chunks]
    documents = [chunk["text"] for chunk in chunks]

    metadatas = [
        {
            "document_id": document_id,
            "page_number": chunk["page_number"],
        }
        for chunk in chunks
    ]

    _get_collection().add(
        documents=documents,
        ids=ids,
        metadatas=metadatas,
    )


def search(query, n_results=8):
    """Retrieve the most relevant chunks across all documents."""

    if not query or not query.strip():
        return []

    try:
        results = _get_collection().query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []

        retrieved_chunks = []

        for text, metadata, distance in zip(
            documents, metadatas, distances
        ):
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
        logger.warning(
            "ChromaDB search failed: %s",
            type(exc).__name__,
        )
        return []


def delete_document_chunks(document_id):
    """Delete all chunks belonging to a document from ChromaDB."""

    try:
        _get_collection().delete(
            where={"document_id": document_id}
        )
    except Exception as exc:
        logger.warning(
            "Failed to delete chunks for document %s from ChromaDB: %s",
            document_id,
            type(exc).__name__,
        )
        raise
