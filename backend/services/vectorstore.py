
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


def add_chunks(chunks, document_id, batch_size=64):
    """Add an iterable of chunks in bounded batches; returns inserted count."""
    from itertools import islice

    target = _get_collection()
    iterator = iter(chunks)
    inserted = 0
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            break
        target.add(
            documents=[chunk["text"] for chunk in batch],
            ids=[str(uuid4()) for _ in batch],
            metadatas=[
                {"document_id": document_id, "page_number": int(chunk["page_number"])}
                for chunk in batch
            ],
        )
        inserted += len(batch)
    return inserted


class VectorStoreUnavailable(RuntimeError):
    """Raised when ChromaDB cannot complete a retrieval operation."""


def search(query, n_results=8):
    """Retrieve relevant chunks; raise on backend failure (never fake an empty index)."""

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
        logger.exception("ChromaDB search failed")
        raise VectorStoreUnavailable("Vector retrieval is temporarily unavailable") from exc


def delete_document_chunks(document_id):
    """Delete all chunks belonging to a document from ChromaDB."""

    try:
        # Chroma metadata may contain either integer or string IDs in tests
        # and older collections; preserve the caller's exact identifier.
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


def indexed_document_ids(document_id=None):
    """Check one document's index without loading collection-wide metadata.

    Passing a document ID uses Chroma's metadata filter and keeps recovery
    memory bounded by that document rather than the entire collection.
    """
    try:
        kwargs = {"include": []}
        if document_id is not None:
            kwargs["where"] = {"document_id": document_id}
        result = _get_collection().get(**kwargs)
        return bool(result.get("ids"))
    except Exception as exc:
        logger.exception("Could not inspect ChromaDB index")
        raise VectorStoreUnavailable("Vector index inspection is unavailable") from exc
