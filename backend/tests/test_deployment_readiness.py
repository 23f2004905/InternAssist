
import os
import pytest
from unittest.mock import MagicMock, patch
from redis.exceptions import ConnectionError as RedisConnectionError

from app import app, db, create_default_admin, normalize_database_url, is_production
from models import User, Conversation, Message
from services.redis_service import (
    get_chat_history,
    save_chat_history,
    delete_chat_history,
    test_redis as ping_redis,
    build_redis_client
)
from services.llm import ask_gemini, get_gemini_client, DEFAULT_GEMINI_MODEL


def test_normalize_database_url():
    """Verify postgres URLs are converted to postgresql:// for SQLAlchemy."""
    assert normalize_database_url("postgres://user:pass@localhost:5432/mydb") == (
        "postgresql://user:pass@localhost:5432/mydb"
    )
    assert normalize_database_url("postgresql://user:pass@localhost:5432/mydb") == (
        "postgresql://user:pass@localhost:5432/mydb"
    )
    assert normalize_database_url("sqlite:///test.db") == "sqlite:///test.db"
    assert normalize_database_url("") == "sqlite:///internassist.db"


def test_production_fails_without_secure_secret_key(monkeypatch):
    """Production mode must fail safely if SECRET_KEY is missing or insecure default."""
    monkeypatch.setenv("FLASK_ENV", "production")
    assert is_production() is True

    # Test with default development key
    with pytest.raises(RuntimeError, match="SECRET_KEY must be securely configured"):
        from app import validate_production_config
        mock_app = MagicMock()
        mock_app.config = {"SECRET_KEY": "development-secret-key"}
        validate_production_config(mock_app)

    # Test with empty key
    with pytest.raises(RuntimeError, match="SECRET_KEY must be securely configured"):
        from app import validate_production_config
        mock_app = MagicMock()
        mock_app.config = {"SECRET_KEY": ""}
        validate_production_config(mock_app)

    # Test with secure key
    mock_app = MagicMock()
    mock_app.config = {"SECRET_KEY": "super-secure-production-random-key"}
    validate_production_config(mock_app)


def test_admin_creation_from_environment_variables(client, monkeypatch):
    """Admin account must be created from environment variables, not hardcoded values."""
    monkeypatch.setenv("ADMIN_EMAIL", "env-admin@internassist.edu")
    monkeypatch.setenv("ADMIN_PASSWORD", "EnvAdminSecurePass123!")
    monkeypatch.setenv("ADMIN_NAME", "Environment Administrator")

    with app.app_context():
        # Ensure user doesn't exist yet
        existing = User.query.filter_by(email="env-admin@internassist.edu").first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

        create_default_admin()

        admin = User.query.filter_by(email="env-admin@internassist.edu").first()
        assert admin is not None
        assert admin.name == "Environment Administrator"
        assert admin.role == "admin"
        assert admin.check_password("EnvAdminSecurePass123!") is True

        # Second run should be idempotent
        create_default_admin()
        assert User.query.filter_by(email="env-admin@internassist.edu").count() == 1


def test_admin_creation_skipped_when_env_vars_missing(client, monkeypatch):
    """When admin credentials are not in environment, admin creation is skipped without error."""
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("DEFAULT_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)

    with app.app_context():
        initial_admin_count = User.query.filter_by(role="admin").count()
        create_default_admin()
        assert User.query.filter_by(role="admin").count() == initial_admin_count


def test_redis_service_outage_handling():
    """Redis service functions must handle connection errors gracefully without raising exceptions."""
    mock_redis = MagicMock()
    mock_redis.ping.side_effect = RedisConnectionError("Connection refused")
    mock_redis.get.side_effect = RedisConnectionError("Connection refused")
    mock_redis.set.side_effect = RedisConnectionError("Connection refused")
    mock_redis.delete.side_effect = RedisConnectionError("Connection refused")

    with patch("services.redis_service.redis_client", mock_redis):
        # ping should return False
        assert ping_redis() is False

        # get should return None on connection failure
        assert get_chat_history(999) is None

        # save should return False without raising
        assert save_chat_history(999, [{"role": "user", "content": "hi"}]) is False

        # delete should return False without raising
        assert delete_chat_history(999) is False


def test_conversation_routes_resilient_to_redis_outage(client):
    """Conversation routes must succeed even when Redis is down or unreachable."""
    # Register and log in a student user
    client.post(
        "/api/auth/register",
        json={
            "name": "Redis Test User",
            "email": "redis-test@example.com",
            "password": "Password123!",
            "role": "student"
        }
    )

    client.post(
        "/api/auth/login",
        json={
            "email": "redis-test@example.com",
            "password": "Password123!"
        }
    )

    # Create a conversation
    create_resp = client.post(
        "/api/conversations",
        json={"title": "Redis Resilience Conversation"}
    )
    assert create_resp.status_code == 201
    conv_id = create_resp.get_json()["conversation"]["id"]

    # Mock Redis failure for all operations
    mock_redis = MagicMock()
    mock_redis.get.side_effect = RedisConnectionError("Connection timed out")
    mock_redis.set.side_effect = RedisConnectionError("Connection timed out")
    mock_redis.delete.side_effect = RedisConnectionError("Connection timed out")

    with patch("services.redis_service.redis_client", mock_redis), \
         patch("app.get_chat_history", return_value=None), \
         patch("app.save_chat_history", return_value=False), \
         patch("app.delete_chat_history", return_value=False):

        # 1. Adding a message should succeed and store in DB despite Redis failure
        msg_resp = client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"role": "user", "content": "Hello world from test"}
        )
        assert msg_resp.status_code == 201
        assert msg_resp.get_json()["data"]["content"] == "Hello world from test"

        # 2. Getting conversation should retrieve messages from DB despite Redis failure
        get_resp = client.get(f"/api/conversations/{conv_id}")
        assert get_resp.status_code == 200
        data = get_resp.get_json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "Hello world from test"

        # 3. Deleting conversation should succeed despite Redis failure
        del_resp = client.delete(f"/api/conversations/{conv_id}")
        assert del_resp.status_code == 200


def test_gemini_missing_api_key(monkeypatch):
    """ask_gemini should safely return fallback message if GEMINI_API_KEY is missing or empty."""
    from services.llm import reset_gemini_client
    reset_gemini_client()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert get_gemini_client() is None
    result = ask_gemini("Context info", "What is the answer?")
    assert result == "Gemini is temporarily unavailable. Please try again."

    # Test with empty string
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    reset_gemini_client()
    assert get_gemini_client() is None
    result_empty = ask_gemini("Context info", "What is the answer?")
    assert result_empty == "Gemini is temporarily unavailable. Please try again."


def test_gemini_successful_response(monkeypatch):
    """ask_gemini should successfully return model text response and format prompt."""
    from services.llm import reset_gemini_client
    reset_gemini_client()

    # Isolate this test from the local .env model override
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "valid-test-key")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is the generated answer from Gemini."
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.llm.get_gemini_client", return_value=mock_client):
        result = ask_gemini("Document text context", "What is the policy?")
        assert result == "This is the generated answer from Gemini."
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args[1]
        assert call_kwargs["model"] == DEFAULT_GEMINI_MODEL
        assert "Document text context" in call_kwargs["contents"]
        assert "What is the policy?" in call_kwargs["contents"]


def test_gemini_api_failure_and_retries(monkeypatch):
    """ask_gemini should retry 3 times on exception and fall back without crashing."""
    from services.llm import reset_gemini_client
    reset_gemini_client()
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key-for-test")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception(
        "API rate limit or connection error"
    )

    with patch("services.llm.get_gemini_client", return_value=mock_client), \
         patch("time.sleep", return_value=None) as mock_sleep:
        result = ask_gemini("Context info", "What is the answer?")
        assert result == "Gemini is temporarily unavailable. Please try again."
        assert mock_client.models.generate_content.call_count == 3
        # Should have slept twice between 3 attempts
        assert mock_sleep.call_count == 2


def test_gemini_lazy_initialization(monkeypatch):
    """Gemini client must be initialized lazily on request, not at import time."""
    from services.llm import reset_gemini_client
    reset_gemini_client()
    monkeypatch.setenv("GEMINI_API_KEY", "lazy-key-test")

    with patch("services.llm.genai.Client") as mock_genai_client:
        mock_genai_client.return_value = MagicMock()
        # Prior to calling get_gemini_client, genai.Client should not be invoked
        assert mock_genai_client.call_count == 0

        client = get_gemini_client()
        assert client is not None
        mock_genai_client.assert_called_once()


def test_gemini_configurable_request_timeout(monkeypatch):
    """Gemini client should pass configurable request timeout in milliseconds to HttpOptions."""
    from services.llm import reset_gemini_client, get_request_timeout
    reset_gemini_client()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-with-timeout")

    # When set to 15 seconds, should parse to 15000 ms
    monkeypatch.setenv("GEMINI_REQUEST_TIMEOUT", "15.0")
    assert get_request_timeout() == 15000

    with patch("services.llm.genai.Client") as mock_genai_client:
        mock_genai_client.return_value = MagicMock()
        get_gemini_client()
        mock_genai_client.assert_called_once()
        _, kwargs = mock_genai_client.call_args
        assert kwargs["http_options"] is not None
        assert kwargs["http_options"].timeout == 15000


def test_gemini_default_model_configuration(monkeypatch):
    """Gemini model name should default to a valid model and allow env override."""
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert DEFAULT_GEMINI_MODEL == "gemini-2.5-flash"


def test_redis_client_configuration_from_url(monkeypatch):
    """build_redis_client should support REDIS_URL environment variable."""
    monkeypatch.setenv("REDIS_URL", "redis://:testpass@example.com:6380/2")

    with patch("redis.Redis.from_url") as mock_from_url:
        build_redis_client()
        mock_from_url.assert_called_once()
        args, kwargs = mock_from_url.call_args
        assert args[0] == "redis://:testpass@example.com:6380/2"
        assert kwargs["decode_responses"] is True
