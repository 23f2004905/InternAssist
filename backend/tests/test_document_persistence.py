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
