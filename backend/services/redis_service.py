import json
import redis

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


def test_redis():
    return redis_client.ping()


def get_chat_history(conversation_id):
    key = f"chat:{conversation_id}"

    data = redis_client.get(key)

    if not data:
        return []

    return json.loads(data)


def save_chat_history(conversation_id, messages):
    key = f"chat:{conversation_id}"

    redis_client.set(
        key,
        json.dumps(messages),
        ex=3600
    )


def delete_chat_history(conversation_id):
    key = f"chat:{conversation_id}"

    redis_client.delete(key)