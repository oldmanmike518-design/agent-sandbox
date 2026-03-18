from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.message import Message

try:
    from redis.asyncio import Redis
    import redis.asyncio as redis_async
except Exception:  # pragma: no cover
    Redis = None  # type: ignore
    redis_async = None  # type: ignore


_redis: Redis | None = None


def has_redis() -> bool:
    return bool(settings.REDIS_URL)


async def get_redis() -> Redis | None:
    global _redis
    if not settings.REDIS_URL:
        return None
    if _redis is None:
        _redis = redis_async.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis


def _hour_bucket(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H")


async def enforce_message_limit(
    agent_id: UUID,
    session: AsyncSession,
    limit_per_hour: int | None = None,
) -> tuple[bool, int, int]:
    """Returns (allowed, remaining, reset_seconds)."""
    limit = limit_per_hour or settings.MESSAGE_LIMIT_PER_HOUR
    now = datetime.now(timezone.utc)

    redis_client = await get_redis()
    if redis_client is not None:
        bucket = _hour_bucket(now)
        key = f"ratelimit:msg:{agent_id}:{bucket}"
        # Use INCR + EXPIRE; set expiry on first increment
        val = await redis_client.incr(key)
        if val == 1:
            # expire a bit after the hour ends
            await redis_client.expire(key, 60 * 60 * 2)

        remaining = max(0, limit - int(val))
        # Reset at next hour boundary
        next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        reset_seconds = int((next_hour - now).total_seconds())
        allowed = int(val) <= limit
        return allowed, remaining, reset_seconds

    # DB fallback
    window_start = now - timedelta(hours=1)
    count_q = select(func.count(Message.id)).where(
        Message.sender_id == agent_id,
        Message.created_at >= window_start,
    )
    count = (await session.execute(count_q)).scalar_one()
    count = int(count)
    allowed = count < limit
    remaining = max(0, limit - count)
    reset_seconds = 60 * 60
    return allowed, remaining, reset_seconds


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
