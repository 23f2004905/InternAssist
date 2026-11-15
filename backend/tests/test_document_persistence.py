import hashlib

from app import db
from models import Document, DocumentFile, User


def test_document_file_bytes_are_persisted_with_document(client):
    with app_context():
        user = User(name="Blob Admin", email="blob-admin@example.com", role="admin")
        user.set_password("TestPassword123!")
        db.session.add(user)
        db.session.flush()
        document = Document(
            title="Persistence test", filename="policy.txt",
            stored_filename="persistence-test.txt", file_type="TXT",
            file_size=12, status="uploaded", uploaded_by_id=user.id,
        )
        db.session.add(document)
        db.session.flush()
        payload = b"hello world!"
        db.session.add(DocumentFile(
            document_id=document.id, content=payload,
            sha256=hashlib.sha256(payload).hexdigest(),
        ))
        db.session.commit()
        stored = db.session.get(DocumentFile, document.id)
        assert stored.content == payload
        assert stored.sha256 == hashlib.sha256(payload).hexdigest()


def app_context():
    from app import app
    return app.app_context()



def _create_legacy_document(email, status="uploaded"):
    from app import db, app
    from models import Document, User

    with app.app_context():
        user = User(name="Legacy Admin", email=email, role="admin")
        user.set_password("TestPassword123!")
        db.session.add(user)
        db.session.flush()
        document = Document(
            title="Legacy SOP", filename="legacy.docx",
            stored_filename=f"{email.split('@')[0]}.docx", file_type="DOCX",
            file_size=128, status=status, uploaded_by_id=user.id,
        )
        db.session.add(document)
        db.session.commit()
        return document.id


def test_legacy_document_without_blob_does_not_block_index_recovery(client, monkeypatch):
    import app as app_module

    _create_legacy_document("legacy-missing@example.com", status="uploaded")
    monkeypatch.setattr(app_module, "indexed_document_ids", lambda document_id: False)
    app_module._index_recovery_state.update(
        status="not_started", restored=0, failed=0, skipped=0, error=None, warning=None
    )

    app_module._recover_chroma_index()

    assert app_module._index_recovery_state["status"] == "ready_with_warnings"
    assert app_module._index_recovery_state["failed"] == 0
    assert app_module._index_recovery_state["skipped"] == 1


def test_legacy_uploaded_document_with_existing_chroma_index_is_preserved(client, monkeypatch):
    import app as app_module
    from app import app as flask_app, db
    from models import Document

    document_id = _create_legacy_document("legacy-indexed@example.com", status="uploaded")
    monkeypatch.setattr(app_module, "indexed_document_ids", lambda requested_id: True)
    app_module._index_recovery_state.update(
        status="not_started", restored=0, failed=0, skipped=0, error=None, warning=None
    )

    app_module._recover_chroma_index()

    with flask_app.app_context():
        assert db.session.get(Document, document_id).status == "indexed"
    assert app_module._index_recovery_state["status"] == "ready"
    assert app_module._index_recovery_state["skipped"] == 0


def test_pending_partial_index_without_blob_is_removed(client, monkeypatch):
    import app as app_module
    from app import app as flask_app, db
    from models import Document

    document_id = _create_legacy_document("pending-partial@example.com", status="pending")
    deleted = []
    monkeypatch.setattr(app_module, "indexed_document_ids", lambda requested_id: True)
    monkeypatch.setattr(app_module, "delete_document_chunks", lambda requested_id: deleted.append(requested_id))
    app_module._index_recovery_state.update(
        status="not_started", restored=0, failed=0, skipped=0, error=None, warning=None
    )

    app_module._recover_chroma_index()

    with flask_app.app_context():
        assert db.session.get(Document, document_id).status == "needs_reupload"
    assert deleted == [document_id]
    assert app_module._index_recovery_state["status"] == "ready_with_warnings"
    assert app_module._index_recovery_state["failed"] == 0
