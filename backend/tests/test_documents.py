import io
from pathlib import Path

import fitz
import pytest
from docx import Document as WordDocument
from pptx import Presentation

import app as app_module
from app import app
from database import db
from models import Document
from services.document_extractor import DocumentExtractionError, extract_document_pages
from services import vectorstore
from conftest import create_user, login


def _files(tmp_path):
    txt = tmp_path / "sample.txt"
    txt.write_text("Internship policy text", encoding="utf-8")
    docx = tmp_path / "sample.docx"
    word = WordDocument()
    word.add_paragraph("DOCX policy text")
    word.save(docx)
    pptx = tmp_path / "sample.pptx"
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "PPTX policy text"
    deck.save(pptx)
    pdf = tmp_path / "sample.pdf"
    pdf_document = fitz.open()
    page = pdf_document.new_page()
    page.insert_text((72, 72), "PDF policy text")
    pdf_document.save(pdf)
    pdf_document.close()
    return [pdf, docx, pptx, txt]


def test_extracts_all_supported_formats_and_rejects_malformed(tmp_path):
    for path in _files(tmp_path):
        pages = extract_document_pages(path, path.suffix[1:])
        assert any(page["text"].strip() for page in pages)
    fake = tmp_path / "fake.pdf"
    fake.write_text("not a pdf")
    with pytest.raises(DocumentExtractionError):
        extract_document_pages(fake, "pdf")


def test_upload_cleanup_download_and_vector_delete(client, monkeypatch, tmp_path):
    create_user("admin@example.com", "admin")
    _, token = login(client, "admin@example.com")
    indexed = []
    deleted = []
    monkeypatch.setattr(app_module, "add_chunks", lambda chunks, document_id: indexed.append(document_id))
    monkeypatch.setattr(app_module, "get_document_chunks", lambda document_id: [])
    monkeypatch.setattr(app_module, "delete_document_chunks", lambda document_id: deleted.append(document_id))
    response = client.post("/api/documents", data={"file": (io.BytesIO(b"policy text"), "policy.txt")}, headers={"X-CSRF-Token": token})
    assert response.status_code == 201
    item = response.get_json()["document"]
    assert indexed == [item["id"]]
    assert client.get(f"/api/documents/{item['id']}/download").status_code == 200
    assert client.delete(f"/api/documents/{item['id']}", headers={"X-CSRF-Token": token}).status_code == 200
    assert deleted == [item["id"]]
    with app.app_context():
        assert db.session.get(Document, item["id"]) is None


def test_failed_indexing_cleans_file_and_record(client, monkeypatch):
    create_user("admin@example.com", "admin")
    _, token = login(client, "admin@example.com")
    monkeypatch.setattr(app_module, "add_chunks", lambda *_: (_ for _ in ()).throw(RuntimeError("index down")))
    response = client.post("/api/documents", data={"file": (io.BytesIO(b"policy text"), "policy.txt")}, headers={"X-CSRF-Token": token})
    assert response.status_code == 500
    with app.app_context():
        assert Document.query.count() == 0
    assert not list(Path(app.config["UPLOAD_FOLDER"]).glob("*.txt"))


def test_page_less_chunk_omits_null_chroma_metadata(monkeypatch):
    captured = {}
    class Collection:
        def add(self, **kwargs):
            captured.update(kwargs)
    monkeypatch.setattr(vectorstore, "_get_collection", lambda: Collection())
    vectorstore.add_chunks([{"text": "TXT text", "page_number": None}], 42)
    assert captured["metadatas"] == [{"document_id": 42}]
