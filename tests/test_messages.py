from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.messages import inbox
from app.models.agent import Agent
from app.models.message import Message


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
    return Agent(id=uuid4(), name="InboxAgent", description="test", is_active=True)


def _message(message_id: int, agent: Agent) -> Message:
    return Message(
        id=message_id,
        sender_id=uuid4(),
        recipient_id=agent.id,
        is_broadcast=False,
        content=f"message {message_id}",
        created_at=datetime.now(timezone.utc),
    )


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
