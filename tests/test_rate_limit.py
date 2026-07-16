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
    assert remaining == 6
    assert reset_seconds == 3600
    assert session.executed is True
    assert rate_limit._redis is None


class _WorkingRedis:
    def __init__(self, value: int) -> None:
        self.value = value
        self.expired = False

    async def incr(self, _key: str) -> int:
        return self.value

    async def expire(self, _key: str, _seconds: int) -> None:
        self.expired = True


def test_redis_limit_boundary_allows_final_message(monkeypatch) -> None:
    redis = _WorkingRedis(value=10)

    async def _get_redis() -> _WorkingRedis:
        return redis

    monkeypatch.setattr(rate_limit, "get_redis", _get_redis)

    allowed, remaining, _reset_seconds = asyncio.run(
        rate_limit.enforce_message_limit(uuid4(), _Session(0), limit_per_hour=10)
    )

    assert allowed is True
    assert remaining == 0


def test_redis_limit_boundary_rejects_next_message(monkeypatch) -> None:
    redis = _WorkingRedis(value=11)

    async def _get_redis() -> _WorkingRedis:
        return redis

    monkeypatch.setattr(rate_limit, "get_redis", _get_redis)

    allowed, remaining, _reset_seconds = asyncio.run(
        rate_limit.enforce_message_limit(uuid4(), _Session(0), limit_per_hour=10)
    )

    assert allowed is False
    assert remaining == 0


def test_database_limit_boundary_reports_post_request_remaining(monkeypatch) -> None:
    async def _no_redis() -> None:
        return None

    monkeypatch.setattr(rate_limit, "get_redis", _no_redis)

    allowed, remaining, _reset_seconds = asyncio.run(
        rate_limit.enforce_message_limit(uuid4(), _Session(9), limit_per_hour=10)
    )

    assert allowed is True
    assert remaining == 0
