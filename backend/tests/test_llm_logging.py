import logging
from types import SimpleNamespace

import pytest
from google.genai import errors

from services import llm

FAKE_KEY = "AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKE12345"
FALLBACK = "Gemini is temporarily unavailable. Please try again."


def client_error(code, status, message):
    return errors.ClientError(
        code, {"error": {"code": code, "status": status, "message": message}}
    )


def server_error(code, status, message):
    return errors.ServerError(
        code, {"error": {"code": code, "status": status, "message": message}}
    )


class FakeModels:
    def __init__(self, exc):
        self.exc = exc
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        raise self.exc


def fake_client(exc):
    return SimpleNamespace(models=FakeModels(exc))


@pytest.fixture(autouse=True)
def isolated_llm(monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    llm.reset_gemini_client()
    caplog.set_level(logging.DEBUG, logger=llm.logger.name)
    yield
    llm.reset_gemini_client()


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(llm, "time", SimpleNamespace(sleep=recorded.append))
    return recorded


def use_client(monkeypatch, exc):
    client = fake_client(exc)
    monkeypatch.setattr(llm, "get_gemini_client", lambda: client)
    return client


def test_logs_status_code_and_message_for_client_error(monkeypatch, caplog, sleeps):
    use_client(
        monkeypatch,
        client_error(403, "PERMISSION_DENIED", "Requests from this referrer are blocked."),
    )

    llm.ask_gemini("ctx", "question")

    assert "type=ClientError" in caplog.text
    assert "code=403" in caplog.text
    assert "status=PERMISSION_DENIED" in caplog.text
    assert "Requests from this referrer are blocked." in caplog.text


def test_api_key_is_redacted_from_logged_output(monkeypatch, caplog, sleeps):
    message = (
        f"API key {FAKE_KEY} rejected for "
        f"https://example.test/v1/models?key={FAKE_KEY} "
        f"x-goog-api-key: {FAKE_KEY}"
    )
    use_client(monkeypatch, client_error(400, "INVALID_ARGUMENT", message))

    llm.ask_gemini("ctx", "question")

    assert FAKE_KEY not in caplog.text
    assert llm.REDACTED in caplog.text
    assert "code=400" in caplog.text


def test_configured_key_is_redacted_even_when_not_google_shaped(monkeypatch, caplog, sleeps):
    monkeypatch.setenv("GEMINI_API_KEY", "plain-secret-value-123")
    use_client(
        monkeypatch,
        client_error(401, "UNAUTHENTICATED", "bad credential plain-secret-value-123 supplied"),
    )

    llm.ask_gemini("ctx", "question")

    assert "plain-secret-value-123" not in caplog.text
    assert llm.REDACTED in caplog.text


def test_non_api_exception_is_logged_with_type_and_redacted_message(monkeypatch, caplog, sleeps):
    use_client(monkeypatch, ValueError(f"bad config using {FAKE_KEY}"))

    llm.ask_gemini("ctx", "question")

    assert "type=ValueError" in caplog.text
    assert "bad config using" in caplog.text
    assert FAKE_KEY not in caplog.text


def test_logged_message_is_single_line_and_truncated():
    exc = RuntimeError("line one\nline two\n" + "x" * 2000)

    description = llm.describe_gemini_error(exc)

    assert "\n" not in description
    assert "line one line two" in description
    assert len(description) < llm.MAX_LOGGED_ERROR_CHARS + 100
    assert description.endswith("...")


def test_key_cut_by_truncation_boundary_is_not_leaked():
    padding = "y" * (llm.MAX_LOGGED_ERROR_CHARS - 10)
    exc = RuntimeError(padding + FAKE_KEY)

    description = llm.describe_gemini_error(exc)

    assert FAKE_KEY[:10] not in description


def test_frontend_response_stays_generic(monkeypatch, sleeps):
    secret_detail = f"PROVIDER-INTERNAL-DETAIL {FAKE_KEY}"
    use_client(monkeypatch, client_error(403, "PERMISSION_DENIED", secret_detail))

    answer = llm.ask_gemini("ctx", "question")

    assert answer == FALLBACK
    assert "PROVIDER-INTERNAL-DETAIL" not in answer
    assert FAKE_KEY not in answer
    assert "403" not in answer


def test_permanent_error_is_not_retried(monkeypatch, sleeps):
    client = use_client(monkeypatch, client_error(400, "INVALID_ARGUMENT", "bad request"))

    answer = llm.ask_gemini("ctx", "question")

    assert answer == FALLBACK
    assert client.models.calls == 1
    assert sleeps == []


def test_transient_error_is_retried_then_falls_back(monkeypatch, caplog, sleeps):
    client = use_client(monkeypatch, server_error(503, "UNAVAILABLE", "model overloaded"))

    answer = llm.ask_gemini("ctx", "question")

    assert answer == FALLBACK
    # Two attempts for the primary and two for the fallback model.
    assert client.models.calls == 4
    assert len(sleeps) == 2
    assert all(1.0 <= delay <= 1.25 for delay in sleeps)
    assert "attempt 1 failed" in caplog.text
    assert "attempt 2 failed" in caplog.text
    assert "code=503" in caplog.text


def test_client_init_failure_is_logged_without_leaking_key(monkeypatch, caplog):
    def boom(**kwargs):
        raise ValueError(f"cannot build client with key={FAKE_KEY}")

    monkeypatch.setattr(llm.genai, "Client", boom)

    assert llm.get_gemini_client() is None
    assert "Failed to initialize Gemini client" in caplog.text
    assert "type=ValueError" in caplog.text
    assert FAKE_KEY not in caplog.text
