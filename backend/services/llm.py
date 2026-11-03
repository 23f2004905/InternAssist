import logging
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

_cached_client = None
_cached_client_key = None


def is_permanent_error(exc):
    """Determine whether an error is non-retriable (permanent client/config error)."""
    if isinstance(exc, errors.APIError):
        # 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found
        if exc.code in (400, 401, 403, 404):
            return True
    if isinstance(exc, (ValueError, TypeError)):
        return True
    return False


def get_request_timeout():
    """Retrieve and parse configured request timeout in milliseconds."""
    timeout_env = os.getenv("GEMINI_REQUEST_TIMEOUT") or os.getenv("GEMINI_TIMEOUT")
    if not timeout_env or not timeout_env.strip():
        return None
    try:
        val = float(timeout_env.strip())
        # If value is less than 1000, treat as seconds and convert to ms
        return int(val * 1000) if val < 1000 else int(val)
    except (ValueError, TypeError):
        logger.warning("Invalid timeout value for Gemini: %s", timeout_env)
        return None


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
        http_options = types.HttpOptions(timeout=timeout_ms) if timeout_ms else None
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
            type(exc).__name__
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

    for i in range(3):
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt
            )

            if response and getattr(response, "text", None):
                return response.text

            return "Gemini is temporarily unavailable. Please try again."

        except Exception as exc:
            logger.warning(
                "Gemini generation attempt %d failed: %s",
                i + 1,
                type(exc).__name__
            )

            if is_permanent_error(exc):
                logger.warning(
                    "Permanent error encountered during Gemini call (%s); aborting retries.",
                    type(exc).__name__
                )
                break

            if i < 2:
                time.sleep(2 * (i + 1))

    return "Gemini is temporarily unavailable. Please try again."
