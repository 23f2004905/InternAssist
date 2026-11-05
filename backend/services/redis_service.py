import json
import logging
import os
import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_CONNECT_TIMEOUT = float(os.getenv("REDIS_CONNECT_TIMEOUT", "2.0"))
REDIS_TIMEOUT = float(os.getenv("REDIS_TIMEOUT", "2.0"))
REDIS_CHAT_TTL = int(os.getenv("REDIS_CHAT_TTL", "3600"))


def build_redis_client():
    """Build a Redis client with configured timeouts and parameters."""
    redis_url = os.getenv("REDIS_URL")
    connect_timeout = float(os.getenv("REDIS_CONNECT_TIMEOUT", "2.0"))
    socket_timeout = float(os.getenv("REDIS_TIMEOUT", "2.0"))
    if redis_url:
        return redis.Redis.from_url(
            redis_url,
           decode_responses=False,
            socket_connect_timeout=connect_timeout,
            socket_timeout=socket_timeout,
        )
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        db=int(os.getenv("REDIS_DB", "0")),
       decode_responses=False,
        socket_connect_timeout=connect_timeout,
        socket_timeout=socket_timeout,
    )


redis_client = build_redis_client()


def test_redis():
    """Ping Redis to test connectivity; return False if unreachable."""
    try:
        return bool(redis_client.ping())
    except (redis.RedisError, OSError, Exception) as exc:
        logger.warning("Redis connectivity test failed: %s", type(exc).__name__)
        return False


def get_chat_history(conversation_id):
    """Retrieve chat history from Redis.

    Returns a list of messages if found or empty on cache miss.
    Returns None if Redis is unavailable or an error occurs.
    """
    key = f"chat:{conversation_id}"
    try:
        data = redis_client.get(key)
        if not data:
            return []
        return json.loads(data)
    except (redis.RedisError, OSError, Exception) as exc:
        logger.warning(
            "Failed to retrieve chat history from Redis for conversation %s: %s",
            conversation_id,
            type(exc).__name__
        )
        return None


def save_chat_history(conversation_id, messages):
    """Save chat history to Redis with TTL.

    Returns True if successfully stored, False otherwise.
    """
    key = f"chat:{conversation_id}"
    try:
        redis_client.set(
            key,
            json.dumps(messages),
            ex=REDIS_CHAT_TTL
        )
        return True
    except (redis.RedisError, OSError, Exception) as exc:
        logger.warning(
            "Failed to save chat history to Redis for conversation %s: %s",
            conversation_id,
            type(exc).__name__
        )
        return False


def delete_chat_history(conversation_id):
    """Delete chat history from Redis.

    Returns True if deleted or key did not exist, False on Redis error.
    """
    key = f"chat:{conversation_id}"
    try:
        redis_client.delete(key)
        return True
    except (redis.RedisError, OSError, Exception) as exc:
        logger.warning(
            "Failed to delete chat history from Redis for conversation %s: %s",
            conversation_id,
            type(exc).__name__
        )
        return False
