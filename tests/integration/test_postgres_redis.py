from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.v1.endpoints.admin import deactivate_agent, revoke_agent_credentials
from app.api.v1.endpoints.agents import rotate_token
from app.api.v1.endpoints.messages import inbox
from app.api.v1.endpoints.register import register_agent
from app.api.v1.endpoints.transactions import send_credits
from app.core.config import settings
from app.models.agent import Agent
from app.models.message import Message
from app.models.rate_limit_bucket import RateLimitBucket
from app.schemas.agent import RegisterRequest, RegisterResponse
from app.schemas.transaction import TransactionSendRequest
from app.services.abuse_control import consume_registration_limit, consume_write_limit
from app.services.auth import create_jwt, get_current_agent
from app.services.rate_limit import close_redis, enforce_message_limit, get_redis
from app.services.readiness import check_readiness


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="requires disposable PostgreSQL and Redis services",
)


def _request(path: str, client_ip: str = "127.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "client": (client_ip, 12345),
        }
    )


async def _session_factory() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], object]]:
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield session_factory, engine
    finally:
        await engine.dispose()


async def _reset_database(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE rate_limit_buckets, event_logs, transactions, messages, agents "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()


async def _new_agent(
    session: AsyncSession,
    *,
    name: str,
    credits: int = 0,
) -> Agent:
    agent = Agent(name=name, description=name, credits_balance=credits)
    session.add(agent)
    await session.flush()
    return agent


def test_migrations_create_expected_schema() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            async with session_factory() as session:
                table_names = set(
                    (
                        await session.execute(
                            text(
                                "SELECT tablename FROM pg_tables "
                                "WHERE schemaname = 'public'"
                            )
                        )
                    ).scalars()
                )
                revision = (
                    await session.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar_one()
                readiness = await check_readiness(session)

            assert {
                "agents",
                "messages",
                "transactions",
                "event_logs",
                "rate_limit_buckets",
            } <= table_names
            assert revision == "0003_agent_credential_version"
            assert readiness.ready is True
            assert readiness.database == "available"
            assert readiness.schema == "current"

    asyncio.run(_run())


def test_duplicate_registration_is_safe_under_concurrency() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)

            async def _register() -> RegisterResponse | Exception:
                async with session_factory() as session:
                    try:
                        return await register_agent(
                            RegisterRequest(name="ConcurrentAgent", description="integration"),
                            _request("/register"),
                            Response(),
                            session=session,
                        )
                    except Exception as exc:
                        return exc

            results = await asyncio.gather(_register(), _register())
            await close_redis()
            successes = [result for result in results if isinstance(result, RegisterResponse)]
            conflicts = [
                result
                for result in results
                if isinstance(result, HTTPException) and result.status_code == 409
            ]

            async with session_factory() as session:
                agent_count = int(
                    (
                        await session.execute(
                            select(func.count(Agent.id)).where(
                                func.lower(Agent.name) == "concurrentagent"
                            )
                        )
                    ).scalar_one()
                )
                minted_credits = int(
                    (
                        await session.execute(
                            select(func.coalesce(func.sum(Agent.credits_balance), 0))
                        )
                    ).scalar_one()
                )

            assert len(successes) == 1
            assert len(conflicts) == 1
            assert agent_count == 1
            assert minted_credits == settings.STARTING_CREDITS

    asyncio.run(_run())


def test_database_registration_limit_is_atomic_under_concurrency() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)
            request = _request("/register")

            async def _consume() -> bool:
                async with session_factory() as session:
                    decision = await consume_registration_limit(
                        request,
                        session,
                        ip_limit=5,
                        global_limit=100,
                        window_seconds=60,
                    )
                    return decision.allowed

            results = await asyncio.gather(*(_consume() for _ in range(20)))

            async with session_factory() as session:
                buckets = {
                    bucket.bucket_key: bucket.count
                    for bucket in (
                        await session.execute(select(RateLimitBucket))
                    ).scalars()
                }

            async with session_factory() as session:
                second_client = await consume_registration_limit(
                    _request("/register", "127.0.0.2"),
                    session,
                    ip_limit=5,
                    global_limit=6,
                    window_seconds=60,
                )

            async with session_factory() as session:
                global_count = (
                    await session.get(RateLimitBucket, "registration:global")
                ).count

            assert results.count(True) == 5
            assert results.count(False) == 15
            assert buckets["registration:global"] == 5
            assert max(
                count
                for key, count in buckets.items()
                if key.startswith("registration:ip:")
            ) == 20
            assert second_client.allowed is True
            assert second_client.scope == "registration-global"
            assert second_client.remaining == 0
            assert global_count == 6

    asyncio.run(_run())


def test_database_write_limit_is_shared_across_agents_and_clients() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)

            async def _consume(client_ip: str, global_limit: int = 100) -> bool:
                async with session_factory() as session:
                    decision = await consume_write_limit(
                        _request("/message/send", client_ip),
                        session,
                        ip_limit=5,
                        global_limit=global_limit,
                        window_seconds=60,
                    )
                    return decision.allowed

            abusive_results = await asyncio.gather(
                *(_consume("127.0.0.10") for _ in range(20))
            )

            async with session_factory() as session:
                buckets = {
                    bucket.bucket_key: bucket.count
                    for bucket in (
                        await session.execute(select(RateLimitBucket))
                    ).scalars()
                }

            async with session_factory() as session:
                second_client = await consume_write_limit(
                    _request("/transaction/send", "127.0.0.11"),
                    session,
                    ip_limit=5,
                    global_limit=6,
                    window_seconds=60,
                )

            assert abusive_results.count(True) == 5
            assert abusive_results.count(False) == 15
            assert buckets["write:global"] == 5
            assert max(
                count
                for key, count in buckets.items()
                if key.startswith("write:ip:")
            ) == 20
            assert second_client.allowed is True
            assert second_client.scope == "write-global"
            assert second_client.remaining == 0

    asyncio.run(_run())


def test_expired_rate_limit_buckets_are_cleaned_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_BUCKET_RETENTION_SECONDS", 0)

    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)
            async with session_factory() as session:
                session.add(
                    RateLimitBucket(
                        bucket_key="registration:ip:expired",
                        count=50,
                        window_ends_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                    )
                )
                await session.commit()

            async with session_factory() as session:
                await consume_registration_limit(
                    _request("/register"),
                    session,
                    ip_limit=5,
                    global_limit=100,
                    window_seconds=60,
                )

            async with session_factory() as session:
                assert (
                    await session.get(RateLimitBucket, "registration:ip:expired")
                ) is None

            async with session_factory() as session:
                session.add(
                    RateLimitBucket(
                        bucket_key="write:ip:expired",
                        count=50,
                        window_ends_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                    )
                )
                await session.commit()

            async with session_factory() as session:
                await consume_write_limit(
                    _request("/ping"),
                    session,
                    ip_limit=5,
                    global_limit=100,
                    window_seconds=60,
                )

            async with session_factory() as session:
                assert (
                    await session.get(RateLimitBucket, "write:ip:expired")
                ) is None

    asyncio.run(_run())


def test_concurrent_transfers_do_not_double_spend() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)
            async with session_factory() as session:
                sender = await _new_agent(session, name="Sender", credits=100)
                recipient = await _new_agent(session, name="Recipient")
                sender_id = sender.id
                recipient_id = recipient.id
                sender_name = sender.name
                sender_credential_version = sender.credential_version
                await session.commit()

            token = create_jwt(
                sender_id,
                sender_name,
                sender_credential_version,
            )
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            authenticated = asyncio.Barrier(2)

            async def _transfer() -> object:
                async with session_factory() as session:
                    try:
                        request = _request("/transaction/send")
                        bound_sender = await get_current_agent(
                            request,
                            creds=creds,
                            session=session,
                        )
                        # Force both requests to cache the original balance
                        # before the limiter commits and participant locks run.
                        await authenticated.wait()
                        return await send_credits(
                            TransactionSendRequest(to_agent_id=recipient_id, amount=80),
                            request,
                            Response(),
                            agent=bound_sender,
                            session=session,
                        )
                    except Exception as exc:
                        return exc

            results = await asyncio.gather(_transfer(), _transfer())
            successes = [result for result in results if not isinstance(result, Exception)]
            insufficient = [
                result
                for result in results
                if isinstance(result, HTTPException)
                and result.status_code == 400
                and result.detail == "Insufficient credits"
            ]

            async with session_factory() as session:
                stored_sender = await session.get(Agent, sender_id)
                stored_recipient = await session.get(Agent, recipient_id)

            assert len(successes) == 1
            assert len(insufficient) == 1
            assert stored_sender is not None
            assert stored_recipient is not None
            assert stored_sender.credits_balance == 20
            assert stored_recipient.credits_balance == 80
            assert stored_sender.credits_balance + stored_recipient.credits_balance == 100

    asyncio.run(_run())


def test_credential_rotation_revocation_and_deactivation() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)
            async with session_factory() as session:
                agent = await _new_agent(session, name="CredentialAgent")
                agent_id = agent.id
                agent_name = agent.name
                credential_version = agent.credential_version
                await session.commit()

            first_token = create_jwt(agent_id, agent_name, credential_version)
            async with session_factory() as session:
                stored_agent = await session.get(Agent, agent_id)
                rotated = await rotate_token(
                    _request("/agents/me/rotate-token"),
                    agent=stored_agent,
                    session=session,
                )

            first_creds = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=first_token,
            )
            rotated_creds = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=rotated.token,
            )
            async with session_factory() as session:
                with pytest.raises(HTTPException, match="Token has been revoked"):
                    await get_current_agent(
                        _request("/agents/me"),
                        creds=first_creds,
                        session=session,
                    )
                assert (
                    await get_current_agent(
                        _request("/agents/me"),
                        creds=rotated_creds,
                        session=session,
                    )
                ).id == agent_id

            async with session_factory() as session:
                revoked = await revoke_agent_credentials(
                    agent_id,
                    _request(f"/admin/agents/{agent_id}/revoke"),
                    session=session,
                )
            assert revoked.is_active is True
            assert revoked.credential_version == credential_version + 2

            async with session_factory() as session:
                with pytest.raises(HTTPException, match="Token has been revoked"):
                    await get_current_agent(
                        _request("/agents/me"),
                        creds=rotated_creds,
                        session=session,
                    )

            async with session_factory() as session:
                deactivated = await deactivate_agent(
                    agent_id,
                    _request(f"/admin/agents/{agent_id}/deactivate"),
                    session=session,
                )
            assert deactivated.is_active is False
            assert deactivated.credential_version == credential_version + 3

    asyncio.run(_run())


def test_concurrent_rotation_allows_exactly_one_replacement() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)
            async with session_factory() as session:
                agent = await _new_agent(session, name="ConcurrentRotateAgent")
                agent_id = agent.id
                token = create_jwt(agent.id, agent.name, agent.credential_version)
                await session.commit()

            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            barrier = asyncio.Barrier(2)

            async def _rotate() -> object:
                async with session_factory() as session:
                    current = await get_current_agent(
                        _request("/agents/me/rotate-token"),
                        creds=credentials,
                        session=session,
                    )
                    await barrier.wait()
                    try:
                        return await rotate_token(
                            _request("/agents/me/rotate-token"),
                            agent=current,
                            session=session,
                        )
                    except Exception as exc:
                        return exc

            results = await asyncio.gather(_rotate(), _rotate())
            successes = [result for result in results if not isinstance(result, Exception)]
            stale = [
                result
                for result in results
                if isinstance(result, HTTPException)
                and result.status_code == 401
                and result.detail == "Token has been revoked or already rotated"
            ]

            async with session_factory() as session:
                stored_agent = await session.get(Agent, agent_id)

            assert len(successes) == 1
            assert len(stale) == 1
            assert stored_agent is not None
            assert stored_agent.credential_version == 2

    asyncio.run(_run())


def test_admin_revoke_cannot_be_undone_by_stale_rotation() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)
            async with session_factory() as session:
                agent = await _new_agent(session, name="RevokeRaceAgent")
                agent_id = agent.id
                token = create_jwt(agent.id, agent.name, agent.credential_version)
                await session.commit()

            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            async with session_factory() as stale_session:
                stale_agent = await get_current_agent(
                    _request("/agents/me/rotate-token"),
                    creds=credentials,
                    session=stale_session,
                )

                async with session_factory() as admin_session:
                    revoked = await revoke_agent_credentials(
                        agent_id,
                        _request(f"/admin/agents/{agent_id}/revoke"),
                        session=admin_session,
                    )
                assert revoked.credential_version == 2

                with pytest.raises(
                    HTTPException,
                    match="Token has been revoked or already rotated",
                ):
                    await rotate_token(
                        _request("/agents/me/rotate-token"),
                        agent=stale_agent,
                        session=stale_session,
                    )

            async with session_factory() as session:
                stored_agent = await session.get(Agent, agent_id)

            assert stored_agent is not None
            assert stored_agent.credential_version == 2

    asyncio.run(_run())


def test_inbox_includes_own_direct_messages_and_broadcasts_only() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            await _reset_database(session_factory)
            async with session_factory() as session:
                reader = await _new_agent(session, name="Reader")
                other = await _new_agent(session, name="Other")
                sender = await _new_agent(session, name="MessageSender")
                session.add_all(
                    [
                        Message(
                            sender_id=sender.id,
                            recipient_id=reader.id,
                            content="for reader",
                            is_broadcast=False,
                        ),
                        Message(
                            sender_id=sender.id,
                            recipient_id=other.id,
                            content="for other",
                            is_broadcast=False,
                        ),
                        Message(
                            sender_id=sender.id,
                            recipient_id=None,
                            content="for everyone",
                            is_broadcast=True,
                        ),
                    ]
                )
                await session.commit()

                response = await inbox(
                    agent=reader,
                    session=session,
                    limit=50,
                    before_id=None,
                    after_id=None,
                )

            assert {item.content for item in response.items} == {
                "for reader",
                "for everyone",
            }

    asyncio.run(_run())


def test_live_redis_rate_limit_boundary() -> None:
    async def _run() -> None:
        async for session_factory, _engine in _session_factory():
            redis_client = await get_redis()
            assert redis_client is not None
            await redis_client.flushdb()

            async with session_factory() as session:
                agent = await _new_agent(session, name="RedisAgent")
                await session.commit()

                first = await enforce_message_limit(agent.id, session, limit_per_hour=2)
                second = await enforce_message_limit(agent.id, session, limit_per_hour=2)
                third = await enforce_message_limit(agent.id, session, limit_per_hour=2)

            assert first[:2] == (True, 1)
            assert second[:2] == (True, 0)
            assert third[:2] == (False, 0)
            await close_redis()

    asyncio.run(_run())
