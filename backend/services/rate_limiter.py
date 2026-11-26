import logging
import os
import time
from typing import Optional
from flask import Flask, jsonify, request, session
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
import redis

logger = logging.getLogger(__name__)


def get_client_ip() -> str:
    """Return client IP safely from remote_addr without relying on spoofable headers.

    Does not trust raw X-Forwarded-For headers from the client to prevent spoofing
    and bypasses. In deployments behind a trusted reverse proxy, Werkzeug ProxyFix
    must be configured at the WSGI layer so request.remote_addr contains the vetted peer IP.
    """
    return request.remote_addr or "127.0.0.1"


def get_ip_key() -> str:
    """Rate limit key strictly based on client IP."""
    return f"ip:{get_client_ip()}"


def get_user_key() -> str:
    """Rate limit key based on authenticated user ID, or fallback to client IP.

    Crucial for university campus networks where dozens or hundreds of students
    share the same public NAT gateway or campus proxy.
    """
    user_id = session.get("user_id")
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_client_ip()}"


def get_login_account_key() -> str:
    """Account-level rate limit key to defend against targeted credential stuffing.

    Extracts the target email from the login JSON payload so that an attacker
    attempting brute force against a specific account is throttled without
    blocking other legitimate students sharing the same campus NAT IP.
    """
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip().lower()
        if email:
            return f"login_account:{email}"
    except Exception:
        pass
    return f"login_ip:{get_client_ip()}"


def get_login_account_limit() -> str:
    """Per-account brute-force protection for login: default 5 requests per minute."""
    return os.getenv("RATELIMIT_LOGIN_ACCOUNT", os.getenv("RATELIMIT_LOGIN", "5/minute"))


def get_login_ip_limit() -> str:
    """Aggregate per-IP ceiling for login to accommodate campus networks: default 60 requests per minute."""
    return os.getenv("RATELIMIT_LOGIN_IP", "60/minute")


def get_login_limit() -> str:
    """Legacy alias for backward compatibility."""
    return get_login_account_limit()


def get_register_limit() -> str:
    """Account creation rate limit: default 10 requests per minute to accommodate campus registrations."""
    return os.getenv("RATELIMIT_REGISTER", "10/minute")


def get_ask_user_limit() -> str:
    """Per-user limit for AI question answering: default 20 requests per minute."""
    return os.getenv("RATELIMIT_ASK_USER", "20/minute")


def get_ask_ip_limit() -> str:
    """Per-IP ceiling for AI question answering: default 100 requests per minute.

    Accommodates multiple concurrent students sharing campus Wi-Fi while capping
    automated denial-of-service floods from a single network.
    """
    return os.getenv("RATELIMIT_ASK_IP", "100/minute")


def get_document_limit() -> str:
    """Document upload rate limit: default 10 uploads per minute per user."""
    return os.getenv("RATELIMIT_DOCUMENTS", "10/minute")


# In-memory quota fallback for isolated testing / local development
_memory_daily_quotas = {}


def check_daily_ai_quota(user_id: int) -> tuple[bool, int, int]:
    """Check and increment per-user daily AI request quota using Redis atomic INCR or local counter.

    Returns (allowed, current_count, daily_limit).
    IMPORTANT: Daily question quotas bound individual user consumption, but are NOT a guaranteed
    Gemini billing cap because individual requests vary in token length, retrieval chunks,
    and prompt complexity. Cost controls must be configured in the Google Cloud / Gemini API Console.
    """
    daily_limit = int(os.getenv("DAILY_AI_QUOTA_PER_USER", "100"))
    if daily_limit <= 0:
        return True, 0, daily_limit

    import datetime
    today = datetime.date.today().isoformat()
    key = f"quota:ai:{user_id}:{today}"

    # Try Redis atomic counter if available
    try:
        from services.redis_service import redis_client, test_redis
        if test_redis():
            count = int(redis_client.incr(key))
            if count == 1:
                redis_client.expire(key, 86400)
            if count > daily_limit:
                return False, count, daily_limit
            return True, count, daily_limit
    except Exception as exc:
        logger.warning("Redis daily quota check failed; using local fallback: %s", exc)

    # In-memory fallback
    current = _memory_daily_quotas.get(key, 0) + 1
    _memory_daily_quotas[key] = current
    if current > daily_limit:
        return False, current, daily_limit
    return True, current, daily_limit


def reset_daily_ai_quota():
    """Reset in-memory daily quota counters (for test teardown)."""
    _memory_daily_quotas.clear()


def resolve_storage_uri(is_prod: bool) -> str:
    """Determine rate limit storage URI.

    In production, shared Redis storage is required. In-memory storage is forbidden.
    In local development or testing, in-memory storage ('memory://') is permitted.
    """
    custom_uri = os.getenv("RATELIMIT_STORAGE_URI")
    if custom_uri:
        if is_prod and custom_uri.strip().lower().startswith("memory://"):
            raise RuntimeError(
                "In-memory rate limit storage ('memory://') is strictly forbidden in production."
            )
        return custom_uri.strip()

    if is_prod:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            return redis_url.strip()
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = os.getenv("RATELIMIT_REDIS_DB", "1")
        redis_password = os.getenv("REDIS_PASSWORD")
        if redis_password:
            return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        return f"redis://{redis_host}:{redis_port}/{redis_db}"

    # For testing and local development, default to in-memory storage
    return "memory://"


# Global Limiter instance configured lazily
limiter = Limiter(
    key_func=get_ip_key,
    headers_enabled=True,
    strategy="moving-window",
)


def init_rate_limiter(app: Flask, is_prod: bool = False):
    """Initialize and configure Flask-Limiter for the application."""
    storage_uri = resolve_storage_uri(is_prod)
    app.config["RATELIMIT_STORAGE_URI"] = storage_uri
    app.config["RATELIMIT_HEADERS_ENABLED"] = True

    # Allow disabling rate limiting explicitly if specified (e.g. specialized bulk benchmarks)
    rate_limit_enabled = os.getenv("RATELIMIT_ENABLED", "true").lower() in ("true", "1", "yes")
    app.config["RATELIMIT_ENABLED"] = rate_limit_enabled

    limiter.init_app(app)

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_exceeded(e: RateLimitExceeded):
        retry_after = 60
        cl = getattr(limiter, "current_limit", None)
        if cl and getattr(cl, "reset_at", None):
            retry_after = max(1, int(cl.reset_at - time.time()))

        response = jsonify({
            "error": "Rate limit exceeded",
            "message": f"Too many requests: {e.description}. Please slow down.",
            "retry_after": retry_after,
        })
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response

    @app.errorhandler(redis.exceptions.ConnectionError)
    @app.errorhandler(redis.exceptions.TimeoutError)
    def handle_redis_storage_error(exc: Exception):
        logger.error("Rate limit Redis storage unavailable: %s", exc)

        # In production or when Redis is the configured rate-limit store,
        # fail safely on expensive operations (/api/ask, /api/documents)
        # to prevent quota exhaustion and system instability.
        if request.path in ("/api/ask", "/api/documents"):
            response = jsonify({
                "error": "Service temporarily unavailable",
                "message": "Rate limiting service is degraded. Expensive operations are temporarily suspended to protect system stability.",
                "retry_after": 30,
            })
            response.status_code = 503
            response.headers["Retry-After"] = "30"
            return response

        fail_open = os.getenv("RATELIMIT_FAIL_OPEN", "false").lower() in ("true", "1")
        if not fail_open and is_prod:
            response = jsonify({
                "error": "Service temporarily unavailable",
                "message": "Rate limiting service is temporarily unavailable.",
                "retry_after": 15,
            })
            response.status_code = 503
            response.headers["Retry-After"] = "15"
            return response

        # Non-expensive endpoints in dev or if explicitly fail_open: raise to default handler
        raise exc
