import json
import os
import redis

_memory_cache = {}

redis_url = os.getenv("REDIS_URL")
redis_client = redis.from_url(
    redis_url,
    decode_responses=True,
    socket_connect_timeout=0.25,
    socket_timeout=0.25
) if redis_url else None


def test_redis():
    return redis_client.ping() if redis_client else False


def get_chat_history(conversation_id):
    key = f"chat:{conversation_id}"

    if redis_client is None:
        return _memory_cache.get(key, [])

    try:
        data = redis_client.get(key)
    except redis.RedisError:
        return _memory_cache.get(key, [])

    if not data:
        return []

    return json.loads(data)


def save_chat_history(conversation_id, messages):
    key = f"chat:{conversation_id}"

    if redis_client is None:
        _memory_cache[key] = messages
        return

    try:
        redis_client.set(
            key,
            json.dumps(messages),
            ex=3600
        )
    except redis.RedisError:
        _memory_cache[key] = messages


def delete_chat_history(conversation_id):
    key = f"chat:{conversation_id}"

    if redis_client is None:
        _memory_cache.pop(key, None)
        return

    try:
        redis_client.delete(key)
    except redis.RedisError:
        _memory_cache.pop(key, None)
