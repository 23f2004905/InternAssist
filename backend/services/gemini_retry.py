"""Bounded retry and fallback for Gemini generation requests."""
import logging
import os
import random
import time
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

DEFAULT_FALLBACK_MODEL = "gemini-3.5-flash-lite"
MAX_ATTEMPTS_PER_MODEL = 2
BASE_DELAY_SECONDS = 1.0
TRANSIENT_CODES = {408, 429, 503, 504}
TRANSIENT_STATUSES = {"RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED"}


class GenerationError(Exception):
    """Generic error safe to convert to the existing frontend fallback."""

    def __init__(self) -> None:
        super().__init__("Answer generation is temporarily unavailable.")


def _code_and_status(exc: BaseException):
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(exc, "status_code", None)
    if isinstance(code, str) and code.isdigit():
        code = int(code)
    status = getattr(exc, "status", None)
    if status is not None and not isinstance(status, str):
        status = getattr(status, "name", None) or str(status)
    return (code if isinstance(code, int) else None,
            status.upper() if isinstance(status, str) else None)


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if any("timeout" in cls.__name__.lower() for cls in type(exc).__mro__):
        return True
    code, status = _code_and_status(exc)
    return code in TRANSIENT_CODES or status in TRANSIENT_STATUSES


def _safe_description(exc: BaseException, formatter=None) -> str:
    if formatter is not None:
        try:
            return formatter(exc)
        except Exception:
            pass
    code, status = _code_and_status(exc)
    # Do not log str(exc): provider messages can contain sensitive values.
    return f"type={type(exc).__name__} code={code} status={status}"


def _retry_model(
    call: Callable[[str], T],
    model: str,
    sleep: Callable[[float], None],
    jitter: float,
    error_formatter=None,
) -> T:
    for attempt in range(1, MAX_ATTEMPTS_PER_MODEL + 1):
        try:
            return call(model)
        except Exception as exc:  # provider SDK and transport exceptions
            details = _safe_description(exc, error_formatter)
            if not is_transient(exc):
                logger.error("Gemini non-retryable error model=%s %s", model, details)
                raise
            logger.warning(
                "Gemini generation attempt %d failed for model %s: %s",
                attempt, model, details,
            )
            if attempt == MAX_ATTEMPTS_PER_MODEL:
                raise
            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            sleep(delay + random.uniform(0.0, jitter * delay))
    raise AssertionError("unreachable")


def generate_with_fallback(
    call: Callable[[str], T],
    primary_model: str,
    fallback_model: Optional[str] = None,
    *,
    sleep: Optional[Callable[[float], None]] = None,
    jitter: float = 0.25,
    error_formatter=None,
) -> T:
    """Try primary, then fallback only after transient primary exhaustion.

    Two attempts at a 25s HTTP timeout per model cap generation at about 102s
    including backoff, below the app's 180s Gunicorn request timeout.
    """
    fallback = fallback_model if fallback_model is not None else (
        os.getenv("GEMINI_FALLBACK_MODEL") or DEFAULT_FALLBACK_MODEL
    )
    sleeper = sleep or time.sleep
    models = [primary_model]
    if fallback and fallback != primary_model:
        models.append(fallback)

    for index, model in enumerate(models):
        try:
            return _retry_model(call, model, sleeper, jitter, error_formatter)
        except Exception as exc:
            if not is_transient(exc):
                raise GenerationError() from None
            if index + 1 < len(models):
                logger.warning("Gemini primary model exhausted; trying configured fallback.")

    logger.error("Gemini generation failed on primary and fallback models.")
    raise GenerationError() from None
