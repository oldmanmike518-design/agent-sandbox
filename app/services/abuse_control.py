from __future__ import annotations

import hmac
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from ipaddress import ip_address

from fastapi import Request
from redis.exceptions import RedisError
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.rate_limit_bucket import RateLimitBucket
from app.services.rate_limit import close_redis, get_redis


logger = logging.getLogger(__name__)

_REDIS_BUCKET_SCRIPT = """
local result = {}
for i, key in ipairs(KEYS) do
  local count = redis.call('INCR', key)
  if count == 1 then
    redis.call('PEXPIRE', key, ARGV[1])
  end
  local ttl = redis.call('PTTL', key)
  if ttl < 0 then
    redis.call('PEXPIRE', key, ARGV[1])
    ttl = tonumber(ARGV[1])
  end
  table.insert(result, count)
  table.insert(result, ttl)
end
return result
"""


@dataclass(frozen=True)
class _LimitRule:
    scope: str
    bucket_key: str
    limit: int


@dataclass(frozen=True)
class RegistrationLimitDecision:
    allowed: bool
    scope: str
    limit: int
    remaining: int
    reset_seconds: int

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_seconds),
            "X-RateLimit-Scope": self.scope,
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.reset_seconds)
        return headers


def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted_networks = settings.trusted_proxy_networks
    if not trusted_networks:
        return peer

    try:
        peer_address = ip_address(peer)
    except ValueError:
        return peer

    if not any(peer_address in network for network in trusted_networks):
        return peer

    forwarded_for = request.headers.get("x-forwarded-for", "")
    try:
        forwarded_chain = [
            ip_address(value.strip())
            for value in forwarded_for.split(",")
            if value.strip()
        ]
    except ValueError:
        return peer

    for candidate in reversed(forwarded_chain):
        if not any(candidate in network for network in trusted_networks):
            return str(candidate)
    return peer


def _client_fingerprint(client_ip: str) -> str:
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        client_ip.encode("utf-8"),
        sha256,
    ).hexdigest()[:32]


def _registration_rules(
    request: Request,
    *,
    ip_limit: int,
    global_limit: int,
) -> list[_LimitRule]:
    fingerprint = _client_fingerprint(get_client_ip(request))
    return [
        _LimitRule("registration-ip", f"registration:ip:{fingerprint}", ip_limit),
        _LimitRule("registration-global", "registration:global", global_limit),
    ]


async def _consume_redis(
    rules: list[_LimitRule],
    *,
    window_seconds: int,
) -> list[tuple[int, int]] | None:
    try:
        redis_client = await get_redis()
        if redis_client is None:
            return None
        keys = [f"abuse:{rule.bucket_key}" for rule in rules]
        raw = await redis_client.eval(
            _REDIS_BUCKET_SCRIPT,
            len(keys),
            *keys,
            window_seconds * 1000,
        )
        return [
            (int(raw[index]), max(1, math.ceil(int(raw[index + 1]) / 1000)))
            for index in range(0, len(raw), 2)
        ]
    except (RedisError, OSError, TimeoutError):
        logger.warning(
            "Redis registration limiter unavailable; using database fallback",
            exc_info=True,
        )
        await close_redis()
        return None


async def _consume_database(
    session: AsyncSession,
    rules: list[_LimitRule],
    *,
    now: datetime,
    window_seconds: int,
) -> list[tuple[int, int]]:
    new_window_end = now + timedelta(seconds=window_seconds)
    consumed: list[tuple[int, int]] = []

    for rule in rules:
        reset_window = RateLimitBucket.window_ends_at <= now
        statement = insert(RateLimitBucket).values(
            bucket_key=rule.bucket_key,
            count=1,
            window_ends_at=new_window_end,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[RateLimitBucket.bucket_key],
            set_={
                "count": case(
                    (reset_window, 1),
                    else_=RateLimitBucket.count + 1,
                ),
                "window_ends_at": case(
                    (reset_window, new_window_end),
                    else_=RateLimitBucket.window_ends_at,
                ),
            },
        ).returning(RateLimitBucket.count, RateLimitBucket.window_ends_at)
        count, window_ends_at = (await session.execute(statement)).one()
        reset_seconds = max(1, math.ceil((window_ends_at - now).total_seconds()))
        consumed.append((int(count), reset_seconds))

    # Persist abuse counters independently of the later registration transaction.
    await session.commit()
    return consumed


async def consume_registration_limit(
    request: Request,
    session: AsyncSession,
    *,
    ip_limit: int | None = None,
    global_limit: int | None = None,
    window_seconds: int | None = None,
    use_redis: bool = True,
) -> RegistrationLimitDecision:
    ip_limit = ip_limit or settings.REGISTRATION_IP_LIMIT_PER_HOUR
    global_limit = global_limit or settings.REGISTRATION_GLOBAL_LIMIT_PER_HOUR
    window_seconds = window_seconds or settings.REGISTRATION_LIMIT_WINDOW_SECONDS
    rules = _registration_rules(
        request,
        ip_limit=ip_limit,
        global_limit=global_limit,
    )

    consumed = None
    if use_redis:
        consumed = await _consume_redis(rules, window_seconds=window_seconds)
    if consumed is None:
        consumed = await _consume_database(
            session,
            rules,
            now=datetime.now(timezone.utc),
            window_seconds=window_seconds,
        )

    decisions = [
        RegistrationLimitDecision(
            allowed=count <= rule.limit,
            scope=rule.scope,
            limit=rule.limit,
            remaining=max(0, rule.limit - count),
            reset_seconds=reset_seconds,
        )
        for rule, (count, reset_seconds) in zip(rules, consumed, strict=True)
    ]
    return next((decision for decision in decisions if not decision.allowed), decisions[0])
