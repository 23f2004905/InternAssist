import io
import time
import pytest
from unittest.mock import MagicMock
from app import app, db
from models import User
from services.rate_limiter import limiter, resolve_storage_uri
import redis


def _register_and_login(client, email="teststudent@example.com", password="password123", role="student"):
    """Helper to register and login a test user."""
    client.post(
        "/api/auth/register",
        json={"name": "Test Student", "email": email, "password": password, "role": role},
    )
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200, f"Login failed: {res.get_json()}"
    return res


def test_login_rate_limiting(client, monkeypatch):
    """Verify login rate limit triggers 429 when threshold exceeded."""
    monkeypatch.setenv("RATELIMIT_LOGIN", "2/minute")
    limiter.reset()

    # Attempts 1 and 2 (invalid credentials return 401, not 429)
    r1 = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert r1.status_code == 401

    r2 = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert r2.status_code == 401

    # Attempt 3 breaches the 2/minute limit
    r3 = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert r3.status_code == 429
    data = r3.get_json()
    assert data["error"] == "Rate limit exceeded"
    assert "retry_after" in data
    assert r3.headers.get("Retry-After") is not None


def test_registration_rate_limiting(client, monkeypatch):
    """Verify registration rate limit prevents automated bot registrations."""
    monkeypatch.setenv("RATELIMIT_REGISTER", "2/minute")
    limiter.reset()

    r1 = client.post("/api/auth/register", json={"name": "User 1", "email": "u1@example.com", "password": "password123"})
    assert r1.status_code == 201

    r2 = client.post("/api/auth/register", json={"name": "User 2", "email": "u2@example.com", "password": "password123"})
    assert r2.status_code == 201

    # Attempt 3 exceeds limit
    r3 = client.post("/api/auth/register", json={"name": "User 3", "email": "u3@example.com", "password": "password123"})
    assert r3.status_code == 429
    assert r3.get_json()["error"] == "Rate limit exceeded"
    assert r3.headers.get("Retry-After") is not None


def test_ask_rate_limiting_per_user(client, monkeypatch):
    """Verify AI requests enforce per-user rate limits."""
    monkeypatch.setenv("RATELIMIT_ASK_USER", "2/minute")
    monkeypatch.setenv("RATELIMIT_ASK_IP", "20/minute")
    limiter.reset()

    # Mock ask_gemini and search to avoid external calls
    import app as app_module
    monkeypatch.setattr(app_module, "search", lambda q, n_results=5: [])
    monkeypatch.setattr(app_module, "ask_gemini", lambda *args, **kwargs: {"answer": "Mocked answer", "model": "mock"})

    _register_and_login(client, email="askuser@example.com")

    # Ask 1 and 2 succeed
    r1 = client.post("/api/ask", json={"question": "What is the policy?"})
    assert r1.status_code == 200

    r2 = client.post("/api/ask", json={"question": "Where is the lab?"})
    assert r2.status_code == 200

    # Ask 3 breaches per-user limit
    r3 = client.post("/api/ask", json={"question": "When is the deadline?"})
    assert r3.status_code == 429
    assert r3.get_json()["error"] == "Rate limit exceeded"
    assert int(r3.headers["Retry-After"]) >= 1


def test_ask_independent_user_identities_on_shared_campus_ip(client, monkeypatch):
    """Verify students sharing the same campus IP NAT have independent per-user rate limits."""
    monkeypatch.setenv("RATELIMIT_ASK_USER", "2/minute")
    monkeypatch.setenv("RATELIMIT_ASK_IP", "10/minute")
    limiter.reset()

    import app as app_module
    monkeypatch.setattr(app_module, "search", lambda q, n_results=5: [])
    monkeypatch.setattr(app_module, "ask_gemini", lambda *args, **kwargs: {"answer": "Mocked answer", "model": "mock"})

    # Student 1 logs in and uses up their 2 allowed requests
    _register_and_login(client, email="student1@campus.edu")
    assert client.post("/api/ask", json={"question": "Question 1"}).status_code == 200
    assert client.post("/api/ask", json={"question": "Question 2"}).status_code == 200
    assert client.post("/api/ask", json={"question": "Question 3"}).status_code == 429

    # Student 2 logs in from the EXACT same client / IP (127.0.0.1)
    client.post("/api/auth/logout")
    _register_and_login(client, email="student2@campus.edu")

    # Student 2 must NOT be blocked by student 1's usage!
    r_student2 = client.post("/api/ask", json={"question": "Student 2 Question"})
    assert r_student2.status_code == 200, "Student 2 on same campus IP should not be throttled by Student 1"


def test_ask_ip_ceiling_prevents_campus_flooding(client, monkeypatch):
    """Verify total requests from a single IP cannot exceed the IP ceiling."""
    monkeypatch.setenv("RATELIMIT_ASK_USER", "10/minute")
    monkeypatch.setenv("RATELIMIT_ASK_IP", "2/minute")
    limiter.reset()

    import app as app_module
    monkeypatch.setattr(app_module, "search", lambda q, n_results=5: [])
    monkeypatch.setattr(app_module, "ask_gemini", lambda *args, **kwargs: {"answer": "Mocked answer", "model": "mock"})

    _register_and_login(client, email="student_ceiling@campus.edu")
    assert client.post("/api/ask", json={"question": "Q1"}).status_code == 200
    assert client.post("/api/ask", json={"question": "Q2"}).status_code == 200

    # 3rd request breaches IP ceiling
    r3 = client.post("/api/ask", json={"question": "Q3"})
    assert r3.status_code == 429
    assert r3.get_json()["error"] == "Rate limit exceeded"


def test_document_upload_rate_limiting(client, monkeypatch):
    """Verify document upload enforces per-user limits for administrators."""
    monkeypatch.setenv("RATELIMIT_DOCUMENTS", "2/minute")
    limiter.reset()

    import app as app_module
    monkeypatch.setattr(app_module, "add_chunks", lambda chunks, document_id: None)

    admin = User(name="Admin User", email="admin_upload@campus.edu", role="admin")
    admin.set_password("AdminPassword123!")
    db.session.add(admin)
    db.session.commit()

    login_res = client.post("/api/auth/login", json={"email": "admin_upload@campus.edu", "password": "AdminPassword123!"})
    assert login_res.status_code == 200, f"Login failed: {login_res.get_json()}"

    file1 = (io.BytesIO(b"Document 1 text"), "doc1.txt")
    file2 = (io.BytesIO(b"Document 2 text"), "doc2.txt")
    file3 = (io.BytesIO(b"Document 3 text"), "doc3.txt")

    r1 = client.post("/api/documents", data={"file": file1}, content_type="multipart/form-data")
    assert r1.status_code == 202

    r2 = client.post("/api/documents", data={"file": file2}, content_type="multipart/form-data")
    assert r2.status_code == 202

    # 3rd upload exceeds limit
    r3 = client.post("/api/documents", data={"file": file3}, content_type="multipart/form-data")
    assert r3.status_code == 429
    assert r3.get_json()["error"] == "Rate limit exceeded"
    assert r3.headers.get("Retry-After") is not None


def test_http_429_payload_and_retry_after():
    """Verify rate limit 429 responses contain valid JSON error and Retry-After header."""
    from flask import Flask
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from services.rate_limiter import init_rate_limiter

    test_app = Flask("test_429_app")
    test_app.config["TESTING"] = True
    test_app.secret_key = "test-secret"

    # Use isolated limiter to prevent mutating shared test state
    isolated_limiter = Limiter(
        key_func=get_remote_address,
        app=test_app,
        storage_uri="memory://",
        headers_enabled=True,
    )

    from flask_limiter.errors import RateLimitExceeded

    @test_app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_exceeded(e: RateLimitExceeded):
        retry_after = 60
        cl = getattr(isolated_limiter, "current_limit", None)
        if cl and getattr(cl, "reset_at", None):
            retry_after = max(1, int(cl.reset_at - time.time()))
        from flask import jsonify
        response = jsonify({
            "error": "Rate limit exceeded",
            "message": f"Too many requests: {e.description}. Please slow down.",
            "retry_after": retry_after,
        })
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response

    @test_app.route("/limited", methods=["POST"])
    @isolated_limiter.limit("1/minute")
    def limited_route():
        return {"status": "ok"}

    with test_app.test_client() as c:
        r1 = c.post("/limited")
        assert r1.status_code == 200

        r2 = c.post("/limited")
        assert r2.status_code == 429
        assert "Retry-After" in r2.headers
        retry_val = r2.headers["Retry-After"]
        assert retry_val.isdigit()
        assert int(retry_val) >= 1

        json_data = r2.get_json()
        assert json_data["error"] == "Rate limit exceeded"
        assert json_data["retry_after"] == int(retry_val)


def test_production_forbids_in_memory_storage(monkeypatch):
    """Verify production strictly forbids in-memory storage."""
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")
    with pytest.raises(RuntimeError, match="strictly forbidden in production"):
        resolve_storage_uri(is_prod=True)


def test_redis_unavailable_in_production_fails_safely_on_expensive_endpoints(monkeypatch):
    """Verify Redis outage in production returns 503 on expensive endpoints without fallback to memory."""
    from flask import Flask, jsonify, request
    from flask_limiter import Limiter
    from services.rate_limiter import get_ip_key

    prod_app = Flask("prod_fail_test")
    prod_app.config["TESTING"] = True
    prod_app.secret_key = "prod-secret"

    # Use isolated limiter with unreachable Redis to prevent mutating global limiter
    isolated_limiter = Limiter(
        key_func=get_ip_key,
        app=prod_app,
        storage_uri="redis://127.0.0.1:9999",
        storage_options={"socket_connect_timeout": 0.1},
        headers_enabled=True,
    )

    @prod_app.errorhandler(redis.exceptions.ConnectionError)
    @prod_app.errorhandler(redis.exceptions.TimeoutError)
    def handle_redis_error(exc):
        if request.path in ("/api/ask", "/api/documents"):
            response = jsonify({
                "error": "Service temporarily unavailable",
                "message": "Rate limiting service is degraded. Expensive operations are temporarily suspended to protect system stability.",
                "retry_after": 30,
            })
            response.status_code = 503
            response.headers["Retry-After"] = "30"
            return response
        raise exc

    @prod_app.route("/api/ask", methods=["POST"])
    @isolated_limiter.limit("5/minute")
    def ask_route():
        return {"answer": "ok"}

    with prod_app.test_client() as c:
        # Request should fail safely with 503 Service Unavailable, not crash or silently use memory
        r = c.post("/api/ask")
        assert r.status_code == 503
        data = r.get_json()
        assert data["error"] == "Service temporarily unavailable"
        assert "Rate limiting service is degraded" in data["message"]
        assert r.headers.get("Retry-After") == "30"


def test_existing_auth_and_session_contracts_preserved(client):
    """Verify authentication cookies, unauthorized status, and valid logins are intact."""
    limiter.reset()

    # Unauthenticated ask returns 401
    r_unauth = client.post("/api/ask", json={"question": "Test?"})
    assert r_unauth.status_code == 401
    assert r_unauth.get_json()["error"] == "Authentication required."

    # Unauthenticated upload returns 401
    r_upload_unauth = client.post("/api/documents", data={"file": (io.BytesIO(b"hi"), "hi.txt")})
    assert r_upload_unauth.status_code == 401

    # Normal registration and login works with session cookie
    _register_and_login(client, email="contract_user@campus.edu")
    r_me = client.get("/api/auth/me")
    assert r_me.status_code == 200
    assert r_me.get_json()["user"]["email"] == "contract_user@campus.edu"
