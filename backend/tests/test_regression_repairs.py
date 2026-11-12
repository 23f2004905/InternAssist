import hashlib
import logging
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from docx import Document as WordDocument
from google.genai import errors

import app as app_module
from app import app, db
from models import Conversation, Document, DocumentFile, Message, User
from services import llm, vectorstore
from services.document_extractor import extract_document_pages
from services.gemini_retry import GenerationError, generate_with_fallback, is_transient


def _register_and_login(client, email, role="student"):
    if role == "admin":
        with app.app_context():
            admin = User(name="Regression Admin", email=email, role="admin")
            admin.set_password("Password123!")
            db.session.add(admin)
            db.session.commit()
    else:
        client.post(
            "/api/auth/register",
            json={
                "name": "Regression User",
                "email": email,
                "password": "Password123!",
                "role": role,
            },
        )
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200


def test_transient_500_502_and_connection_errors_retry():
    class ServerErr(Exception):
        def __init__(self, code, status):
            self.code = code
            self.status = status

    assert is_transient(ServerErr(500, "INTERNAL")) is True
    assert is_transient(ServerErr(502, "BAD_GATEWAY")) is True
    assert is_transient(ConnectionResetError("peer reset")) is True

    calls = []

    def flaky(model):
        calls.append(model)
        if len(calls) == 1:
            raise ConnectionResetError("connection dropped")
        return "recovered"

    sleeps = []
    assert (
        generate_with_fallback(
            flaky, "primary", "fallback", sleep=sleeps.append, jitter=0
        )
        == "recovered"
    )
    assert calls == ["primary", "primary"]
    assert sleeps == [1.0]


def test_empty_gemini_model_env_uses_default_and_empty_text_falls_back(monkeypatch):
    llm.reset_gemini_client()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.setenv("GEMINI_MODEL", "   ")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "fallback-model")

    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs["model"])
            if kwargs["model"] == llm.DEFAULT_GEMINI_MODEL:
                return SimpleNamespace(text="", candidates=[], prompt_feedback=None)
            return SimpleNamespace(text="Fallback answer")

    fake_client = SimpleNamespace(models=FakeModels())
    monkeypatch.setattr(llm, "get_gemini_client", lambda: fake_client)
    monkeypatch.setattr(llm, "time", SimpleNamespace(sleep=lambda _: None))

    answer = llm.ask_gemini("Context", "Question")
    assert answer == "Fallback answer"
    assert calls == [
        llm.DEFAULT_GEMINI_MODEL,
        llm.DEFAULT_GEMINI_MODEL,
        "fallback-model",
    ]


def test_vectorstore_embed_texts_retries_and_redacts_secrets(monkeypatch, caplog):
    fake_key = "AIzaSyEMBEDSECRETKEY1234567890123456"
    monkeypatch.setenv("GEMINI_API_KEY", fake_key)
    caplog.set_level(logging.DEBUG, logger="services.gemini_retry")
    caplog.set_level(logging.DEBUG, logger=vectorstore.logger.name)

    attempts = {"count": 0}

    class FakeModels:
        def embed_content(self, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise errors.ServerError(
                    503,
                    {"error": {"code": 503, "status": "UNAVAILABLE", "message": f"overloaded for key={fake_key}"}},
                )
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.25] * 768)])

    fake_client = SimpleNamespace(models=FakeModels())
    monkeypatch.setattr(llm, "get_gemini_client", lambda: fake_client)
    monkeypatch.setattr(vectorstore.time, "sleep", lambda _: None)

    vectors = vectorstore._embed_texts(["internship policy"], "RETRIEVAL_QUERY")
    assert attempts["count"] == 2
    assert len(vectors) == 1
    assert len(vectors[0]) == 768
    assert fake_key not in caplog.text


def test_vectorstore_search_redacts_error_logs(monkeypatch, caplog):
    fake_key = "AIzaSySEARCHSECRETKEY123456789012345"
    monkeypatch.setenv("GEMINI_API_KEY", fake_key)
    caplog.set_level(logging.ERROR, logger=vectorstore.logger.name)

    def fail_embed(texts, task_type):
        raise RuntimeError(f"failed calling https://generativelanguage.googleapis.com/?key={fake_key}")

    monkeypatch.setattr(vectorstore, "_embed_texts", fail_embed)
    try:
        vectorstore.search("internship rules")
        assert False, "Expected VectorStoreUnavailable"
    except vectorstore.VectorStoreUnavailable:
        pass

    assert fake_key not in caplog.text
    assert llm.REDACTED in caplog.text


def test_docx_preserves_order_and_deduplicates_merged_cells(tmp_path):
    doc_path = tmp_path / "ordered.docx"
    doc = WordDocument()
    doc.add_paragraph("Section 1: Overview")
    table = doc.add_table(rows=1, cols=2)
    cell_a = table.cell(0, 0)
    cell_b = table.cell(0, 1)
    cell_a.merge(cell_b)
    cell_a.text = "Merged Header"
    doc.add_paragraph("Section 2: Closing")
    doc.save(doc_path)

    pages = extract_document_pages(str(doc_path), "docx")
    assert len(pages) == 1
    text = pages[0]["text"]
    assert text.index("Section 1: Overview") < text.index("Merged Header") < text.index("Section 2: Closing")
    assert text.count("Merged Header") == 1


def test_txt_extractor_handles_cp1252(tmp_path):
    txt_path = tmp_path / "legacy.txt"
    txt_path.write_bytes("Internship guide \u201cofficial\u201d".encode("cp1252"))
    pages = extract_document_pages(str(txt_path), "txt")
    assert "Internship guide" in pages[0]["text"]
    assert "\u201cofficial\u201d" in pages[0]["text"]


def test_upload_non_ascii_filename_and_malformed_json(client, monkeypatch):
    _register_and_login(client, "nonascii-admin@example.com", role="admin")
    monkeypatch.setattr(app_module, "add_chunks", lambda chunks, document_id: 1)

    upload = client.post(
        "/api/documents",
        data={"file": (BytesIO(b"Policy details"), "文档.txt")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 202
    assert upload.get_json()["document"]["filename"] == "document.txt"

    # Malformed / null JSON fields should return 400, not 500
    bad_reg = client.post(
        "/api/auth/register",
        data="not-json",
        content_type="application/json",
    )
    assert bad_reg.status_code == 400

    bad_ask = client.post(
        "/api/ask",
        json={"question": None},
    )
    assert bad_ask.status_code == 400


def test_ask_with_conversation_history_and_source_context(client):
    _register_and_login(client, "followup@example.com", role="student")

    with app.app_context():
        admin = User(name="Doc Owner", email="docowner@example.com", role="admin")
        admin.set_password("Password123!")
        db.session.add(admin)
        db.session.flush()
        doc = Document(
            title="Internship SOP",
            filename="sop.pdf",
            stored_filename="sop-stored.pdf",
            file_type="PDF",
            file_size=100,
            status="indexed",
            uploaded_by_id=admin.id,
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    conv_resp = client.post("/api/conversations", json={"title": "Follow-up test"})
    conv_id = conv_resp.get_json()["conversation"]["id"]
    client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"role": "user", "content": "What is the minimum internship duration?"},
    )
    client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"role": "assistant", "content": "The minimum duration is 8 weeks."},
    )
    client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Are log books mandatory?"},
    )

    captured = {}

    def fake_ask_gemini(context, question, history=None):
        captured["context"] = context
        captured["question"] = question
        captured["history"] = history
        return "Yes, weekly log books are mandatory."

    fake_chunks = [
        {"text": "Weekly log books must be signed.", "document_id": doc_id, "page_number": 3, "distance": 0.1},
        {"text": "Invalid doc id chunk.", "document_id": "non-int-id", "page_number": 1, "distance": 0.2},
    ]

    with patch("app.search", return_value=fake_chunks) as mock_search, \
         patch("app.ask_gemini", side_effect=fake_ask_gemini):
        resp = client.post(
            "/api/ask",
            json={"question": "Are log books mandatory?", "conversation_id": conv_id},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["answer"] == "Yes, weekly log books are mandatory."
    assert "[Source: sop.pdf, Page 3]" in captured["context"]
    # Duplicate trailing user message excluded; prior 2 turns included
    assert len(captured["history"]) == 2
    assert captured["history"][0]["content"] == "What is the minimum internship duration?"
    # Short follow-up query enriched with previous user question
    assert "minimum internship duration" in mock_search.call_args[0][0]
    assert data["citations"][0]["document_name"] == "sop.pdf"
    assert data["citations"][1]["document_name"] == "Unknown document"


def test_index_recovery_handles_corrupt_doc_without_blocking_valid_doc(client, monkeypatch):
    with app.app_context():
        admin = User(name="Recovery Admin", email="rec-admin@example.com", role="admin")
        admin.set_password("Password123!")
        db.session.add(admin)
        db.session.flush()

        bad_doc = Document(
            title="Corrupt PDF",
            filename="bad.pdf",
            stored_filename="bad.pdf",
            file_type="PDF",
            file_size=10,
            status="pending",
            uploaded_by_id=admin.id,
        )
        good_doc = Document(
            title="Good TXT",
            filename="good.txt",
            stored_filename="good.txt",
            file_type="TXT",
            file_size=24,
            status="pending",
            uploaded_by_id=admin.id,
        )
        db.session.add_all([bad_doc, good_doc])
        db.session.flush()
        bad_bytes = b"not a valid pdf"
        good_bytes = b"Internship policy text."
        db.session.add_all([
            DocumentFile(document_id=bad_doc.id, content=bad_bytes, sha256=hashlib.sha256(bad_bytes).hexdigest()),
            DocumentFile(document_id=good_doc.id, content=good_bytes, sha256=hashlib.sha256(good_bytes).hexdigest()),
        ])
        db.session.commit()
        bad_id, good_id = bad_doc.id, good_doc.id

    monkeypatch.setattr(app_module, "indexed_document_ids", lambda doc_id: False)
    monkeypatch.setattr(app_module, "delete_document_chunks", lambda doc_id: None)
    monkeypatch.setattr(app_module, "add_chunks", lambda chunks, doc_id, batch_size=32: len(list(chunks)))
    app_module._index_recovery_state.update(
        status="not_started", restored=0, failed=0, skipped=0, error=None, warning=None
    )

    app_module._recover_chroma_index()

    with app.app_context():
        assert db.session.get(Document, bad_id).status == "needs_reupload"
        assert db.session.get(Document, good_id).status == "indexed"
    assert app_module._index_recovery_state["status"] == "ready_with_warnings"
    assert app_module._index_recovery_state["restored"] == 1
    assert app_module._index_recovery_state["skipped"] == 1


def test_ask_filters_error_history_and_expands_referential_followup(client):
    _register_and_login(client, "quality@example.com", role="student")
    conv_resp = client.post("/api/conversations", json={"title": "Quality test"})
    conv_id = conv_resp.get_json()["conversation"]["id"]

    client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"role": "user", "content": "What is the summer internship stipend?"},
    )
    client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"role": "assistant", "content": "Gemini is temporarily unavailable. Please try again."},
    )

    captured = {}

    def fake_ask_gemini(context, question, history=None):
        captured["question"] = question
        captured["history"] = history
        return "You need an offer letter and bank form."

    fake_chunks = [
        {"text": "Submit your offer letter for stipend processing.", "document_id": 1, "page_number": 2, "distance": 0.1}
    ]
    followup = "What documents do I need to submit for that?"
    with patch("app.search", return_value=fake_chunks) as mock_search, \
         patch("app.ask_gemini", side_effect=fake_ask_gemini):
        resp = client.post(
            "/api/ask",
            json={"question": followup, "conversation_id": conv_id},
        )

    assert resp.status_code == 200
    assert "summer internship stipend" in mock_search.call_args[0][0]
    assert captured["question"] == followup
    assert captured["history"] == [{"role": "user", "content": "What is the summer internship stipend?"}]


