import re
import pytest
from app import app, db
from models import User
from services.rate_limiter import limiter


def test_session_regeneration_on_login(client):
    """Verify session ID is regenerated upon login to prevent session fixation attacks."""
    limiter.reset()

    with app.app_context():
        user = User(name="Regen User", email="regen@campus.edu", role="student")
        user.set_password("SecurePassword123!")
        db.session.add(user)
        db.session.commit()

    # Step 1: Pre-populate session with an unauthenticated attacker key
    with client.session_transaction() as sess:
        sess["pre_login_token"] = "attacker_controlled_value"
        initial_sid = getattr(sess, "sid", None)

    # Step 2: Login as user
    login_res = client.post(
        "/api/auth/login",
        json={"email": "regen@campus.edu", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200

    # Step 3: Verify the session identifier changed and old data was cleared
    with client.session_transaction() as sess:
        post_login_sid = getattr(sess, "sid", None)
        assert post_login_sid is not None
        assert post_login_sid != initial_sid, "Session ID must be regenerated on login"
        assert "pre_login_token" not in sess, "Pre-login session state must be cleared"
        assert sess.get("user_id") is not None, "Authenticated user_id must be populated"


def test_registration_input_validation_password_length(client):
    """Verify registration rejects passwords shorter than 8 or longer than 128 characters."""
    limiter.reset()

    # Too short (< 8)
    r_short = client.post(
        "/api/auth/register",
        json={"name": "Short Pass", "email": "short@campus.edu", "password": "short", "role": "student"},
    )
    assert r_short.status_code == 400
    assert "at least 8 characters" in r_short.get_json()["error"]

    # Too long (> 128)
    long_pass = "A" * 129
    r_long = client.post(
        "/api/auth/register",
        json={"name": "Long Pass", "email": "long@campus.edu", "password": long_pass, "role": "student"},
    )
    assert r_long.status_code == 400
    assert "cannot exceed 128 characters" in r_long.get_json()["error"]


def test_registration_input_validation_email_format(client):
    """Verify registration validates email address format and length."""
    limiter.reset()

    invalid_emails = [
        "not-an-email",
        "missingatsign.com",
        "user@nodomain",
        "@missinguser.com",
        "spaces in@email.com",
        "user@.com",
    ]

    for bad_email in invalid_emails:
        r = client.post(
            "/api/auth/register",
            json={"name": "Bad Email", "email": bad_email, "password": "ValidPassword123!", "role": "student"},
        )
        assert r.status_code == 400, f"Expected 400 for bad email: {bad_email}"
        assert "valid email address" in r.get_json()["error"]

    # Email too long (> 254 chars per RFC 5321)
    too_long_email = "a" * 245 + "@campus.edu"
    r_len = client.post(
        "/api/auth/register",
        json={"name": "Long Email", "email": too_long_email, "password": "ValidPassword123!", "role": "student"},
    )
    assert r_len.status_code == 400


def test_registration_input_validation_name_length(client):
    """Verify registration rejects names longer than 100 characters."""
    limiter.reset()

    long_name = "N" * 101
    r = client.post(
        "/api/auth/register",
        json={"name": long_name, "email": "validname@campus.edu", "password": "ValidPassword123!", "role": "student"},
    )
    assert r.status_code == 400
    assert "Name cannot exceed 100 characters" in r.get_json()["error"]


def test_ask_question_length_validation(client, monkeypatch):
    """Verify /api/ask rejects oversized questions exceeding 4000 characters."""
    limiter.reset()

    import app as app_module
    monkeypatch.setattr(app_module, "search", lambda q, n_results=5: [])
    monkeypatch.setattr(app_module, "ask_gemini", lambda *args, **kwargs: {"answer": "Mocked", "model": "mock"})

    r_reg = client.post(
        "/api/auth/register",
        json={"name": "Ask Student", "email": "ask_length@campus.edu", "password": "ValidPassword123!", "role": "student"},
    )
    assert r_reg.status_code == 201

    r_log = client.post("/api/auth/login", json={"email": "ask_length@campus.edu", "password": "ValidPassword123!"})
    assert r_log.status_code == 200

    oversized_question = "Explain this policy: " + ("x" * 4000)
    r = client.post("/api/ask", json={"question": oversized_question})
    assert r.status_code == 400
    assert "exceeds maximum allowed length" in r.get_json()["error"]


def test_security_headers_present_on_responses(client):
    """Verify defensive HTTP security headers are attached to responses."""
    r = client.get("/")
    assert r.status_code == 200

    headers = r.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in headers.get("Content-Security-Policy", "")


def test_origin_verification_rejects_untrusted_cross_origin(client):
    """Verify state-modifying requests from untrusted origins receive 403 Forbidden."""
    # 1. Untrusted origin on POST /api/auth/login
    r_untrusted = client.post(
        "/api/auth/login",
        json={"email": "any@campus.edu", "password": "anypassword"},
        headers={"Origin": "https://malicious-phishing-site.com"},
    )
    assert r_untrusted.status_code == 403
    assert r_untrusted.get_json()["error"] == "Cross-origin request forbidden."

    # 2. Trusted CORS origin on POST /api/auth/login
    r_trusted = client.post(
        "/api/auth/login",
        json={"email": "any@campus.edu", "password": "anypassword"},
        headers={"Origin": "http://localhost:5173"},
    )
    # Reaches application handler (401 invalid creds, not 403 origin rejected)
    assert r_trusted.status_code == 401

    # 3. Same-origin (request.host_url)
    r_same_origin = client.post(
        "/api/auth/login",
        json={"email": "any@campus.edu", "password": "anypassword"},
        headers={"Origin": "http://localhost"},
    )
    assert r_same_origin.status_code == 401


def test_account_level_login_rate_limiting_with_campus_nat(client, monkeypatch):
    """Verify credential stuffing attacks on one account do not block other students on the same campus IP."""
    monkeypatch.setenv("RATELIMIT_LOGIN_ACCOUNT", "2/minute")
    monkeypatch.setenv("RATELIMIT_LOGIN_IP", "10/minute")
    limiter.reset()

    # Attacker targets victim@campus.edu
    r1 = client.post("/api/auth/login", json={"email": "victim@campus.edu", "password": "wrong"})
    assert r1.status_code == 401
    r2 = client.post("/api/auth/login", json={"email": "victim@campus.edu", "password": "wrong"})
    assert r2.status_code == 401

    # 3rd attempt on victim account hits per-account rate limit
    r3 = client.post("/api/auth/login", json={"email": "victim@campus.edu", "password": "wrong"})
    assert r3.status_code == 429
    assert r3.get_json()["error"] == "Rate limit exceeded"

    # Innocent student logging into a DIFFERENT account from the exact same client IP is NOT blocked
    r_innocent = client.post("/api/auth/login", json={"email": "innocent_student@campus.edu", "password": "wrong"})
    assert r_innocent.status_code == 401, "Innocent student on campus NAT should not be locked out by attacker"


def test_session_regeneration_failure_aborts_login(client, monkeypatch):
    """Verify that if session regeneration fails, login is safely aborted without adopting the old session."""
    limiter.reset()

    with app.app_context():
        user = User(name="Failing Regen User", email="fail_regen@campus.edu", role="student")
        user.set_password("ValidPassword123!")
        db.session.add(user)
        db.session.commit()

    import app as app_module
    # Force session regeneration to simulate failure
    monkeypatch.setattr(app_module, "regenerate_session", lambda: False)

    res = client.post(
        "/api/auth/login",
        json={"email": "fail_regen@campus.edu", "password": "ValidPassword123!"},
    )
    assert res.status_code == 500
    assert "secure session initialization error" in res.get_json()["error"]

    # Verify session was NOT authenticated
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_csrf_and_origin_verification_matrix(client, monkeypatch):
    """Verify CSRF token and Origin verification matrix on cookie-authenticated mutating routes."""
    limiter.reset()
    monkeypatch.setitem(app.config, "CSRF_STRICT", True)

    # Register and login to establish authenticated session
    client.post(
        "/api/auth/register",
        json={"name": "CSRF User", "email": "csrf_matrix@campus.edu", "password": "ValidPassword123!", "role": "student"},
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email": "csrf_matrix@campus.edu", "password": "ValidPassword123!"},
    )
    assert login_res.status_code == 200
    csrf_token = login_res.get_json()["csrf_token"]
    assert csrf_token is not None

    # Scenario 1: Reject Origin: null strictly
    r_null = client.post(
        "/api/conversations",
        json={"title": "Test Null"},
        headers={"Origin": "null", "X-CSRF-Token": csrf_token},
    )
    assert r_null.status_code == 403
    assert "strictly forbidden" in r_null.get_json()["error"]

    # Scenario 2: Missing Origin + missing CSRF token
    r_missing_both = client.post(
        "/api/conversations",
        json={"title": "Test Missing"},
    )
    assert r_missing_both.status_code == 403

    # Scenario 3: Trusted Origin + invalid CSRF token -> Rejected!
    r_bad_csrf = client.post(
        "/api/conversations",
        json={"title": "Test Bad CSRF"},
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "invalid_forged_token"},
    )
    assert r_bad_csrf.status_code == 403
    assert "Invalid CSRF token" in r_bad_csrf.get_json()["error"]

    # Scenario 4: Valid CSRF token without Origin -> Accepted (for CLI/mobile tools)
    r_valid_no_origin = client.post(
        "/api/conversations",
        json={"title": "Test Valid No Origin"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r_valid_no_origin.status_code == 201

    # Scenario 5: Trusted Origin + valid CSRF token -> Accepted
    r_both_valid = client.post(
        "/api/conversations",
        json={"title": "Test Both Valid"},
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_token},
    )
    assert r_both_valid.status_code == 201


def test_faculty_registration_requires_verification_code(client, monkeypatch):
    """Verify public registration cannot grant faculty privileges without valid verification code."""
    limiter.reset()
    monkeypatch.setenv("FACULTY_REGISTRATION_KEY", "INSTITUTE_FACULTY_2026_SECRET")

    # Attempt 1: Register as faculty without code -> 403
    r_no_code = client.post(
        "/api/auth/register",
        json={"name": "Fake Faculty", "email": "fake_faculty@campus.edu", "password": "ValidPassword123!", "role": "faculty"},
    )
    assert r_no_code.status_code == 403
    assert "faculty verification code" in r_no_code.get_json()["error"]

    # Attempt 2: Register as faculty with wrong code -> 403
    r_wrong_code = client.post(
        "/api/auth/register",
        json={"name": "Wrong Code Faculty", "email": "wrong_fac@campus.edu", "password": "ValidPassword123!", "role": "faculty", "faculty_code": "wrong_pass"},
    )
    assert r_wrong_code.status_code == 403

    # Attempt 3: Register as faculty with correct code -> 201
    r_valid_code = client.post(
        "/api/auth/register",
        json={"name": "Real Faculty", "email": "real_fac@campus.edu", "password": "ValidPassword123!", "role": "faculty", "faculty_code": "INSTITUTE_FACULTY_2026_SECRET"},
    )
    assert r_valid_code.status_code == 201
    assert r_valid_code.get_json()["user"]["role"] == "faculty"


def test_daily_ai_quota_enforcement(client, monkeypatch):
    """Verify daily AI request quota bounds per-user consumption with clean 429 and Retry-After."""
    from services.rate_limiter import reset_daily_ai_quota
    reset_daily_ai_quota()
    limiter.reset()

    # Configure daily quota to 2 questions
    monkeypatch.setenv("DAILY_AI_QUOTA_PER_USER", "2")

    import app as app_module
    monkeypatch.setattr(app_module, "search", lambda q, n_results=5: [])
    monkeypatch.setattr(app_module, "ask_gemini", lambda *args, **kwargs: {"answer": "Mocked", "model": "mock"})

    client.post(
        "/api/auth/register",
        json={"name": "Quota Student", "email": "quota_student@campus.edu", "password": "ValidPassword123!", "role": "student"},
    )
    client.post("/api/auth/login", json={"email": "quota_student@campus.edu", "password": "ValidPassword123!"})

    # Question 1: OK
    r1 = client.post("/api/ask", json={"question": "Question 1"})
    assert r1.status_code == 200

    # Question 2: OK
    r2 = client.post("/api/ask", json={"question": "Question 2"})
    assert r2.status_code == 200

    # Question 3: Exceeds daily quota -> 429
    r3 = client.post("/api/ask", json={"question": "Question 3"})
    assert r3.status_code == 429
    data = r3.get_json()
    assert "Daily AI question quota exceeded" in data["error"]
    assert data["daily_limit"] == 2
    assert int(r3.headers.get("Retry-After")) >= 1


def test_admin_conversations_oversight_and_privacy(client):
    """Verify admin conversation oversight endpoint enforces RBAC and preserves student message privacy."""
    from models import Conversation, Message

    # 1. Unauthenticated -> 401
    r_unauth = client.get("/api/admin/conversations")
    assert r_unauth.status_code == 401

    # 2. Student user -> 403 Forbidden
    client.post(
        "/api/auth/register",
        json={"name": "Privacy Student", "email": "student_privacy@campus.edu", "password": "ValidPassword123!", "role": "student"},
    )
    client.post("/api/auth/login", json={"email": "student_privacy@campus.edu", "password": "ValidPassword123!"})

    # Student creates a conversation
    r_conv = client.post("/api/conversations", json={"title": "Private Internship Dilemma"})
    assert r_conv.status_code == 201
    conv_id = r_conv.get_json()["conversation"]["id"]

    # Student posts a private message
    client.post(f"/api/conversations/{conv_id}/messages", json={"role": "user", "content": "Confidential student situation details"})

    # Student cannot access admin conversations oversight
    r_student_access = client.get("/api/admin/conversations")
    assert r_student_access.status_code == 403

    # 3. Admin user -> 200 OK with privacy-preserving metadata
    client.post("/api/auth/logout")

    admin = User(name="Oversight Admin", email="admin_oversight@campus.edu", role="admin")
    admin.set_password("ValidPassword123!")
    db.session.add(admin)
    db.session.commit()

    client.post("/api/auth/login", json={"email": "admin_oversight@campus.edu", "password": "ValidPassword123!"})

    r_admin = client.get("/api/admin/conversations")
    assert r_admin.status_code == 200
    conversations = r_admin.get_json()["conversations"]
    assert len(conversations) >= 1

    target_conv = next((c for c in conversations if c["id"] == conv_id), None)
    assert target_conv is not None
    assert target_conv["title"] == "Private Internship Dilemma"
    assert target_conv["user_name"] == "Privacy Student"
    assert target_conv["user_email"] == "student_privacy@campus.edu"
    assert target_conv["message_count"] == 1
    # Privacy check: message body is NOT returned in the conversation list
    assert "messages" not in target_conv
    assert "content" not in target_conv
