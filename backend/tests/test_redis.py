import redis

from services import redis_service


class BrokenRedis:
    def get(self, _key):
        raise redis.RedisError("offline")
    def set(self, *_args, **_kwargs):
        raise redis.RedisError("offline")
    def delete(self, _key):
        raise redis.RedisError("offline")


class WorkingRedis:
    def __init__(self):
        self.values = {}
    def get(self, key):
        return self.values.get(key)
    def set(self, key, value, **_kwargs):
        self.values[key] = value
    def delete(self, key):
        self.values.pop(key, None)


def test_redis_disabled_and_unavailable_never_supply_partial_history(monkeypatch):
    monkeypatch.setattr(redis_service, "redis_client", None)
    assert redis_service.get_chat_history(1) is None
    redis_service.save_chat_history(1, [{"role": "user"}])
    assert redis_service.get_chat_history(1) is None
    monkeypatch.setattr(redis_service, "redis_client", BrokenRedis())
    assert redis_service.get_chat_history(1) is None
    redis_service.save_chat_history(1, [{"role": "user"}])
    recovered = WorkingRedis()
    monkeypatch.setattr(redis_service, "redis_client", recovered)
    complete_history = [{"role": "user", "content": "question"}, {"role": "assistant", "content": "answer"}]
    redis_service.save_chat_history(1, complete_history)
    assert redis_service.get_chat_history(1) == complete_history
    redis_service.delete_chat_history(1)
    assert redis_service.get_chat_history(1) is None
