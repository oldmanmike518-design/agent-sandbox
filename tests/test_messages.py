from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response
from pydantic import ValidationError

from app.api.v1.endpoints.messages import inbox, send_message
from app.core.config import settings
from app.models.agent import Agent
from app.models.event_log import EventLog
from app.models.message import Message
from app.schemas.message import MessageSendRequest
from app.services.abuse_control import RateLimitDecision


class _Scalars:
    def __init__(self, values: list[Message]) -> None:
        self.values = values

    def all(self) -> list[Message]:
        return self.values


class _Result:
    def __init__(self, values: list[Message]) -> None:
        self.values = values

    def scalars(self) -> _Scalars:
        return _Scalars(self.values)


class _Session:
    def __init__(self, values: list[Message]) -> None:
        self.values = values
        self.queries: list[object] = []

    async def execute(self, query: object) -> _Result:
        self.queries.append(query)
        return _Result(self.values)


def _agent() -> Agent:
    return Agent(
        id=uuid4(),
        name="InboxAgent",
        description="test",
        is_active=True,
        messages_sent=0,
        messages_received=0,
    )


def _message(message_id: int, agent: Agent) -> Message:
    return Message(
        id=message_id,
        sender_id=uuid4(),
        recipient_id=agent.id,
        is_broadcast=False,
        content=f"message {message_id}",
        created_at=datetime.now(timezone.utc),
    )


class _ScalarResult:
    def __init__(self, value: Agent | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Agent | None:
        return self.value


class _MessageSession:
    def __init__(self, results: list[Agent | None] | None = None) -> None:
        self.results = list(results or [])
        self.queries: list[object] = []
        self.added: list[object] = []
        self.committed = False

    async def execute(self, query: object) -> _ScalarResult:
        self.queries.append(query)
        return _ScalarResult(self.results.pop(0))

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for value in self.added:
            if isinstance(value, Message):
                value.id = 1
                value.created_at = datetime.now(timezone.utc)

    async def commit(self) -> None:
        self.committed = True


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/message/send",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


def _set_message_limit(
    monkeypatch: pytest.MonkeyPatch,
    *,
    allowed: bool = True,
    remaining: int = 9,
    reset_seconds: int = 3600,
) -> None:
    async def _limit(*_args: object, **_kwargs: object) -> tuple[bool, int, int]:
        return allowed, remaining, reset_seconds

    async def _write_limit(
        *_args: object,
        **_kwargs: object,
    ) -> RateLimitDecision:
        return RateLimitDecision(True, "write-ip", 60, 59, 60)

    monkeypatch.setattr("app.api.v1.endpoints.messages.enforce_message_limit", _limit)
    monkeypatch.setattr("app.api.v1.endpoints.messages.consume_write_limit", _write_limit)


def test_message_request_rejects_unknown_and_ambiguous_recipient_fields() -> None:
    with pytest.raises(ValidationError):
        MessageSendRequest.model_validate(
            {"to_agent": "IntendedPrivateRecipient", "content": "private content"}
        )

    with pytest.raises(ValidationError):
        MessageSendRequest(
            to_agent_id=uuid4(),
            to_agent_name="IntendedPrivateRecipient",
            content="private content",
        )


def test_direct_send_updates_counters_event_and_rate_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_message_limit(monkeypatch, remaining=8, reset_seconds=120)
    sender = _agent()
    recipient = _agent()
    recipient.name = "Recipient"
    session = _MessageSession([recipient])
    response = Response()

    result = asyncio.run(
        send_message(
            MessageSendRequest(
                to_agent_id=recipient.id,
                subject="  hello  ",
                content="  private message  ",
            ),
            _request(),
            response,
            agent=sender,
            session=session,
        )
    )

    assert result.recipient_id == recipient.id
    assert result.is_broadcast is False
    assert result.subject == "hello"
    assert result.content == "private message"
    assert sender.messages_sent == 1
    assert recipient.messages_received == 1
    assert session.committed is True
    assert [type(value) for value in session.added] == [Message, EventLog]
    assert response.headers["X-RateLimit-Remaining"] == "8"
    assert response.headers["X-RateLimit-Reset"] == "120"


def test_broadcast_send_has_no_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_message_limit(monkeypatch)
    sender = _agent()
    session = _MessageSession()

    result = asyncio.run(
        send_message(
            MessageSendRequest(content="broadcast"),
            _request(),
            Response(),
            agent=sender,
            session=session,
        )
    )

    assert result.recipient_id is None
    assert result.is_broadcast is True
    assert sender.messages_sent == 1
    assert session.queries == []
    assert session.committed is True


def test_rate_limit_rejection_carries_headers_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_message_limit(monkeypatch, allowed=False, remaining=0, reset_seconds=42)
    session = _MessageSession()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            send_message(
                MessageSendRequest(content="blocked"),
                _request(),
                Response(),
                agent=_agent(),
                session=session,
            )
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {
        "X-RateLimit-Limit": str(settings.MESSAGE_LIMIT_PER_HOUR),
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": "42",
        "X-RateLimit-Scope": "message-agent",
    }
    assert session.added == []
    assert session.committed is False


def test_shared_write_limit_rejects_before_agent_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _denied(*_args: object, **_kwargs: object) -> RateLimitDecision:
        return RateLimitDecision(False, "write-ip", 60, 0, 11)

    async def _unexpected_agent_limit(*_args: object, **_kwargs: object):
        raise AssertionError("per-agent limiter must not run after shared denial")

    monkeypatch.setattr("app.api.v1.endpoints.messages.consume_write_limit", _denied)
    monkeypatch.setattr(
        "app.api.v1.endpoints.messages.enforce_message_limit",
        _unexpected_agent_limit,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            send_message(
                MessageSendRequest(content="blocked"),
                _request(),
                Response(),
                agent=_agent(),
                session=_MessageSession(),
            )
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "11"
    assert exc_info.value.headers["X-RateLimit-Scope"] == "write-ip"


def test_post_limit_message_failure_includes_consumed_budget_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_message_limit(monkeypatch, remaining=8, reset_seconds=120)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            send_message(
                MessageSendRequest(to_agent_id=uuid4(), content="missing recipient"),
                _request(),
                Response(),
                agent=_agent(),
                session=_MessageSession([None]),
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.headers["X-RateLimit-Scope"] == "message-agent"
    assert exc_info.value.headers["X-RateLimit-Remaining"] == "8"


def test_inbox_rejects_mixed_forward_and_backward_cursors() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            inbox(
                agent=_agent(),
                session=_Session([]),
                limit=50,
                before_id=10,
                after_id=5,
            )
        )

    assert exc_info.value.status_code == 400


def test_forward_cursor_returns_ascending_messages_and_next_after_id() -> None:
    agent = _agent()
    session = _Session([_message(5, agent), _message(6, agent)])

    response = asyncio.run(
        inbox(
            agent=agent,
            session=session,
            limit=50,
            before_id=None,
            after_id=4,
        )
    )

    assert [item.id for item in response.items] == [5, 6]
    assert response.next_after_id == 6
    assert response.next_before_id is None
    assert "messages.id ASC" in str(session.queries[0])


def test_backward_cursor_preserves_existing_pagination_contract() -> None:
    agent = _agent()
    session = _Session([_message(9, agent), _message(8, agent)])

    response = asyncio.run(
        inbox(
            agent=agent,
            session=session,
            limit=2,
            before_id=10,
            after_id=None,
        )
    )

    assert [item.id for item in response.items] == [9, 8]
    assert response.next_before_id == 8
    assert response.next_after_id is None
    assert "messages.id DESC" in str(session.queries[0])
