from conftest import create_user, csrf, login
from app import app
from database import db
from models import User


def test_register_login_restore_logout_and_csrf(client):
    assert client.post("/api/auth/register", json={}).status_code == 403
    token = csrf(client)
    response = client.post("/api/auth/register", json={"name": "Student", "email": "new@example.com", "password": "password123", "role": "student"}, headers={"X-CSRF-Token": token})
    assert response.status_code == 201
    response, token = login(client, "new@example.com")
    assert response.status_code == 200
    assert client.get("/api/auth/me").get_json()["user"]["email"] == "new@example.com"
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_inactive_session_and_role_authorization(client):
    user_id = create_user()
    response, token = login(client)
    assert response.status_code == 200
    with app.app_context():
        db.session.get(User, user_id).active = False
        db.session.commit()
    assert client.get("/api/documents").status_code == 401

    create_user("faculty@example.com", "faculty")
    response, _ = login(client, "faculty@example.com")
    assert response.status_code == 200
    assert client.get("/api/admin/users").status_code == 403


def test_auth_rejects_malformed_fields_and_short_passwords(client):
    token = csrf(client)
    malformed = client.post(
        "/api/auth/register",
        json={"name": {"unexpected": True}, "email": ["bad"], "password": 123456, "role": "student"},
        headers={"X-CSRF-Token": token},
    )
    assert malformed.status_code == 400
    short = client.post(
        "/api/auth/register",
        json={"name": "Student", "email": "student@example.com", "password": "12345", "role": "student"},
        headers={"X-CSRF-Token": token},
    )
    assert short.status_code == 400
    bad_login = client.post(
        "/api/auth/login",
        json={"email": {"unexpected": True}, "password": ["bad"]},
        headers={"X-CSRF-Token": token},
    )
    assert bad_login.status_code == 401
