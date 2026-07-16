from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response

from app.api.v1.endpoints.ping import ping
from app.models.agent import Agent
from app.models.event_log import EventLog
from app.services.abuse_control import RateLimitDecision


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/ping",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


def _agent() -> Agent:
    return Agent(
        id=uuid4(),
        name="PingAgent",
        description="test",
        is_active=True,
    )


def test_ping_applies_shared_write_limit_and_records_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allowed(*_args: object, **_kwargs: object) -> RateLimitDecision:
        return RateLimitDecision(True, "write-ip", 60, 12, 41)

    monkeypatch.setattr("app.api.v1.endpoints.ping.consume_write_limit", _allowed)
    agent = _agent()
    response = Response()
    session = _Session()

    result = asyncio.run(ping(_request(), response, agent=agent, session=session))

    assert result["status"] == "ok"
    assert "server_time" in result
    assert isinstance(agent.last_seen_at, datetime)
    assert response.headers["X-RateLimit-Scope"] == "write-ip"
    assert response.headers["X-RateLimit-Remaining"] == "12"
    assert any(isinstance(item, EventLog) for item in session.added)
    assert session.committed is True


def test_ping_shared_write_denial_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _denied(*_args: object, **_kwargs: object) -> RateLimitDecision:
        return RateLimitDecision(False, "write-global", 600, 0, 8)

    monkeypatch.setattr("app.api.v1.endpoints.ping.consume_write_limit", _denied)
    agent = _agent()
    session = _Session()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(ping(_request(), Response(), agent=agent, session=session))

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "8"
    assert agent.last_seen_at is None
    assert session.added == []
    assert session.committed is False
