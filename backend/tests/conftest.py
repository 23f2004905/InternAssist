import os

import pytest

_runtime = os.path.join(os.path.dirname(__file__), ".runtime")
os.makedirs(_runtime, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_runtime, 'test.db')}"
os.environ["UPLOAD_FOLDER"] = os.path.join(_runtime, "uploads")
os.environ["SECRET_KEY"] = "test-secret"
os.environ.pop("DEFAULT_ADMIN_EMAIL", None)
os.environ.pop("DEFAULT_ADMIN_PASSWORD", None)

from app import app as flask_app
from database import db
from models import User


@pytest.fixture(autouse=True)
def clean_database():
    flask_app.config.update(TESTING=True)
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()


@pytest.fixture
def client():
    return flask_app.test_client()


def csrf(client):
    return client.get("/api/auth/csrf").get_json()["csrf_token"]


def create_user(email="student@example.com", role="student", active=True):
    with flask_app.app_context():
        user = User(name="Test User", email=email, role=role, active=active)
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        return user.id


def login(client, email="student@example.com"):
    token = csrf(client)
    response = client.post("/api/auth/login", json={"email": email, "password": "password123"}, headers={"X-CSRF-Token": token})
    return response, response.get_json().get("csrf_token")
