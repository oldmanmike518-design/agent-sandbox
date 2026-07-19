from __future__ import annotations

import hmac
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from ipaddress import ip_address

from fastapi import Request
from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.rate_limit_bucket import RateLimitBucket


@dataclass(frozen=True)
class _LimitRule:
    scope: str
    bucket_key: str
    limit: int


@dataclass(frozen=True)
class RateLimitDecision:
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


@dataclass(frozen=True)
class VerificationLimitDecision:
    allowed: bool
    headers: dict[str, str]
    bucket_windows: list[dict]


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


def _hierarchical_rules(
    request: Request,
    *,
    bucket_prefix: str,
    scope_prefix: str,
    client_limit: int,
    global_limit: int,
) -> list[_LimitRule]:
    fingerprint = _client_fingerprint(get_client_ip(request))
    return [
        _LimitRule(
            f"{scope_prefix}-ip",
            f"{bucket_prefix}:ip:{fingerprint}",
            client_limit,
        ),
        _LimitRule(
            f"{scope_prefix}-global",
            f"{bucket_prefix}:global",
            global_limit,
        ),
    ]


async def _consume_rule(
    session: AsyncSession,
    rule: _LimitRule,
    *,
    now: datetime,
    window_seconds: int,
) -> RateLimitDecision:
    new_window_end = now + timedelta(seconds=window_seconds)
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
    count = int(count)
    return RateLimitDecision(
        allowed=count <= rule.limit,
        scope=rule.scope,
        limit=rule.limit,
        remaining=max(0, rule.limit - count),
        reset_seconds=max(1, math.ceil((window_ends_at - now).total_seconds())),
    )


async def _consume_database(
    session: AsyncSession,
    rules: list[_LimitRule],
    *,
    now: datetime,
    window_seconds: int,
    cleanup_expired: bool,
) -> list[RateLimitDecision]:
    if cleanup_expired:
        retention_cutoff = now - timedelta(
            seconds=settings.RATE_LIMIT_BUCKET_RETENTION_SECONDS
        )
        await session.execute(
            delete(RateLimitBucket).where(
                RateLimitBucket.window_ends_at < retention_cutoff
            )
        )

    decisions: list[RateLimitDecision] = []
    for rule in rules:
        decision = await _consume_rule(
            session,
            rule,
            now=now,
            window_seconds=window_seconds,
        )
        decisions.append(decision)
        # An already-limited client must not consume the shared global budget.
        if not decision.allowed:
            break

    # Persist abuse counters independently of the later application transaction.
    await session.commit()
    return decisions


async def _consume_hierarchical_limit(
    request: Request,
    session: AsyncSession,
    *,
    bucket_prefix: str,
    scope_prefix: str,
    client_limit: int,
    global_limit: int,
    window_seconds: int,
    cleanup_expired: bool,
) -> RateLimitDecision:
    rules = _hierarchical_rules(
        request,
        bucket_prefix=bucket_prefix,
        scope_prefix=scope_prefix,
        client_limit=client_limit,
        global_limit=global_limit,
    )
    decisions = await _consume_database(
        session,
        rules,
        now=datetime.now(timezone.utc),
        window_seconds=window_seconds,
        cleanup_expired=cleanup_expired,
    )
    denied = next((decision for decision in decisions if not decision.allowed), None)
    if denied is not None:
        return denied
    return min(decisions, key=lambda decision: decision.remaining)


async def consume_registration_limit(
    request: Request,
    session: AsyncSession,
    *,
    ip_limit: int | None = None,
    global_limit: int | None = None,
    window_seconds: int | None = None,
) -> RateLimitDecision:
    ip_limit = ip_limit or settings.REGISTRATION_IP_LIMIT_PER_HOUR
    global_limit = global_limit or settings.REGISTRATION_GLOBAL_LIMIT_PER_HOUR
    window_seconds = window_seconds or settings.REGISTRATION_LIMIT_WINDOW_SECONDS
    return await _consume_hierarchical_limit(
        request,
        session,
        bucket_prefix="registration",
        scope_prefix="registration",
        client_limit=ip_limit,
        global_limit=global_limit,
        window_seconds=window_seconds,
        cleanup_expired=True,
    )


async def consume_write_limit(
    request: Request,
    session: AsyncSession,
    *,
    ip_limit: int | None = None,
    global_limit: int | None = None,
    window_seconds: int | None = None,
) -> RateLimitDecision:
    return await _consume_hierarchical_limit(
        request,
        session,
        bucket_prefix="write",
        scope_prefix="write",
        client_limit=ip_limit or settings.WRITE_IP_LIMIT_PER_MINUTE,
        global_limit=global_limit or settings.WRITE_GLOBAL_LIMIT_PER_MINUTE,
        window_seconds=window_seconds or settings.WRITE_LIMIT_WINDOW_SECONDS,
        cleanup_expired=True,
    )


async def consume_verification_limit(
    request: Request,
) -> VerificationLimitDecision:
    now = datetime.now(timezone.utc)
    rules = _hierarchical_rules(
        request,
        bucket_prefix="verify",
        scope_prefix="verify",
        client_limit=settings.VERIFY_RUNS_PER_IP_PER_DAY,
        global_limit=settings.VERIFY_RUNS_GLOBAL_PER_DAY,
    )
    keys = [rule.bucket_key for rule in rules]
    async with AsyncSessionLocal() as limiter_session:
        decision: RateLimitDecision | None = None
        for rule in rules:
            decision = await _consume_rule(
                limiter_session,
                rule,
                now=now,
                window_seconds=86400,
            )
            if not decision.allowed:
                await limiter_session.commit()
                return VerificationLimitDecision(
                    False, decision.headers, []
                )
        rows = (
            await limiter_session.execute(
                select(RateLimitBucket).where(
                    RateLimitBucket.bucket_key.in_(keys)
                )
            )
        ).scalars().all()
        windows = [
            {
                "key": row.bucket_key,
                "window_ends_at": row.window_ends_at.isoformat(),
            }
            for row in rows
        ]
        await limiter_session.commit()
        assert decision is not None
        return VerificationLimitDecision(
            True, decision.headers, windows
        )


async def refund_verification_limit(
    session: AsyncSession, bucket_windows: list[dict]
) -> None:
    for entry in bucket_windows:
        await session.execute(
            update(RateLimitBucket)
            .where(
                RateLimitBucket.bucket_key == entry["key"],
                RateLimitBucket.window_ends_at
                == datetime.fromisoformat(entry["window_ends_at"]),
                RateLimitBucket.count > 0,
            )
            .values(count=RateLimitBucket.count - 1)
        )
