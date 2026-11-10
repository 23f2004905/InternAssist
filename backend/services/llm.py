import logging
import os
import re
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from services.gemini_retry import (
    DEFAULT_FALLBACK_MODEL,
    GenerationError,
    generate_with_fallback,
)

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 25.0
MAX_REQUEST_TIMEOUT_MS = 25_000

REDACTED = "[REDACTED]"
MAX_LOGGED_ERROR_CHARS = 500

# Google API keys look like "AIza..." and may also show up as key=... / x-goog-api-key: ...
_GOOGLE_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_\-]{20,}")
_KEY_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)((?:x-goog-api-key|api[_-]?key|key)\s*[=:]\s*)[^\s&\"',;]+"
)

_cached_client = None
_cached_client_key = None


def redact_secrets(text):
    """Strip the configured Gemini API key and key-shaped strings from text."""
    text = "" if text is None else str(text)

    known_keys = [os.getenv("GEMINI_API_KEY")]
    if _cached_client_key:
        known_keys.append(_cached_client_key[0])
    for key in known_keys:
        if key and key.strip():
            text = text.replace(key, REDACTED).replace(key.strip(), REDACTED)

    text = _GOOGLE_KEY_PATTERN.sub(REDACTED, text)
    return _KEY_ASSIGNMENT_PATTERN.sub(lambda m: m.group(1) + REDACTED, text)


def describe_gemini_error(exc):
    """Return a single-line, secret-free summary of an exception for logs only.

    Includes the exception type, HTTP/status code and provider message. Never
    return this to API clients.
    """
    code = getattr(exc, "code", None)
    status = redact_secrets(getattr(exc, "status", None) or "")
    message = getattr(exc, "message", None) or str(exc)

    # Redact before truncating so a key cut at the boundary can't leak partially.
    message = redact_secrets(" ".join(str(message).split()))
    if len(message) > MAX_LOGGED_ERROR_CHARS:
        message = message[:MAX_LOGGED_ERROR_CHARS] + "..."

    return "type=%s code=%s status=%s message=%s" % (
        type(exc).__name__,
        code,
        status or None,
        message,
    )


def is_permanent_error(exc):
    """Determine whether an error is non-retriable (permanent client/config error)."""
    if isinstance(exc, errors.APIError):
        # 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found
        code = getattr(exc, "code", None)
        if code in (400, 401, 403, 404):
            return True
        if isinstance(exc, errors.ClientError) and code != 429:
            return True
    if isinstance(exc, (ValueError, TypeError)):
        return True
    return False


def get_request_timeout():
    """Retrieve and parse configured request timeout in milliseconds."""
    timeout_env = os.getenv("GEMINI_REQUEST_TIMEOUT") or os.getenv("GEMINI_TIMEOUT")
    if not timeout_env or not timeout_env.strip():
        return int(DEFAULT_REQUEST_TIMEOUT_SECONDS * 1000)
    try:
        val = float(timeout_env.strip())
        if val <= 0:
            return int(DEFAULT_REQUEST_TIMEOUT_SECONDS * 1000)
        # If value is less than 1000, treat as seconds and convert to ms.
        configured_ms = int(val * 1000) if val < 1000 else int(val)
        # Bound each network call so primary + fallback fit the 180s Gunicorn limit.
        return max(1_000, min(configured_ms, MAX_REQUEST_TIMEOUT_MS))
    except (ValueError, TypeError):
        logger.warning("Invalid timeout value for Gemini: %s", timeout_env)
        return int(DEFAULT_REQUEST_TIMEOUT_SECONDS * 1000)


def get_gemini_client():
    """Safely obtain or lazily initialize a Gemini client instance."""
    global _cached_client, _cached_client_key

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        return None

    timeout_ms = get_request_timeout()
    cache_key = (api_key.strip(), timeout_ms)

    if _cached_client is not None and _cached_client_key == cache_key:
        return _cached_client

    try:
        http_options = types.HttpOptions(
            timeout=timeout_ms,
            # The application retry loop owns retries; one SDK attempt avoids
            # hidden retries multiplying the total request duration.
            retry_options=types.HttpRetryOptions(attempts=1),
        )
        client = genai.Client(
            api_key=api_key.strip(),
            http_options=http_options
        )
        _cached_client = client
        _cached_client_key = cache_key
        return _cached_client
    except Exception as exc:
        logger.warning(
            "Failed to initialize Gemini client: %s",
            describe_gemini_error(exc)
        )
        return None


def reset_gemini_client():
    """Reset the cached client instance (primarily for testing)."""
    global _cached_client, _cached_client_key
    _cached_client = None
    _cached_client_key = None


def ask_gemini(context, question):
    """Answer a user question based strictly on retrieved document context."""
    context = (context or "")[:12000]

    prompt = f"""
You are InternAssist, an AI assistant for an internship placement platform.

Answer ONLY using the context below.
If the answer isn't in the context, say you don't have enough information.

Context:
{context}

Question:
{question}
"""

    gemini_client = get_gemini_client()
    if not gemini_client:
        logger.warning("Gemini API key is missing or client is unavailable.")
        return "Gemini is temporarily unavailable. Please try again."

    model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL") or DEFAULT_FALLBACK_MODEL

    try:
        response = generate_with_fallback(
            lambda selected_model: gemini_client.models.generate_content(
                model=selected_model,
                contents=prompt,
            ),
            primary_model=model_name,
            fallback_model=fallback_model,
            sleep=time.sleep,
            error_formatter=describe_gemini_error,
        )
    except GenerationError:
        return "Gemini is temporarily unavailable. Please try again."

    if response and getattr(response, "text", None):
        return response.text
    return "Gemini is temporarily unavailable. Please try again."
