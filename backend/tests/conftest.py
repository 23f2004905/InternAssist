import os
import pytest
from pathlib import Path

TEST_DB_DIR = Path(__file__).parent / "test_data"
TEST_DB_DIR.mkdir(exist_ok=True)

TEST_DB_PATH = TEST_DB_DIR / "test_internassist.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.resolve()}"
os.environ["CHROMA_DB_PATH"] = str(TEST_DB_DIR / "chroma_test_db")

from app import app, db


@pytest.fixture(scope="session", autouse=True)
def test_database():
    test_uploads = TEST_DB_DIR / "uploads"
    test_sessions = TEST_DB_DIR / "sessions"
    test_uploads.mkdir(exist_ok=True)
    test_sessions.mkdir(exist_ok=True)

    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        SESSION_TYPE="filesystem",
        SESSION_FILE_DIR=str(test_sessions),
        UPLOAD_FOLDER=str(test_uploads),
    )

    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(test_database):
    with app.app_context():
        db.drop_all()
        db.create_all()

    with app.test_client() as test_client:
        yield test_client
