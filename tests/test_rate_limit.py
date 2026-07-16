from __future__ import annotations

import asyncio
from uuid import uuid4

from redis.exceptions import ConnectionError

from app.services import rate_limit


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class _Session:
    def __init__(self, message_count: int) -> None:
        self.message_count = message_count
        self.executed = False

    async def execute(self, _query: object) -> _ScalarResult:
        self.executed = True
        return _ScalarResult(self.message_count)


class _BrokenRedis:
    async def incr(self, _key: str) -> int:
        raise ConnectionError("Redis unavailable")

    async def aclose(self) -> None:
        return None


def test_redis_failure_uses_database_fallback(monkeypatch) -> None:
    session = _Session(message_count=3)
    broken_redis = _BrokenRedis()

    async def _get_broken_redis() -> _BrokenRedis:
        return broken_redis

    monkeypatch.setattr(rate_limit, "get_redis", _get_broken_redis)
    monkeypatch.setattr(rate_limit, "_redis", broken_redis)

    allowed, remaining, reset_seconds = asyncio.run(
        rate_limit.enforce_message_limit(uuid4(), session, limit_per_hour=10)
    )

    assert allowed is True
    assert remaining == 7
    assert reset_seconds == 3600
    assert session.executed is True
    assert rate_limit._redis is None
