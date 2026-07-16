from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request

from app.api.v1.endpoints.transactions import send_credits
from app.models.agent import Agent
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionSendRequest


class _Scalars:
    def __init__(self, values: list[Agent]) -> None:
        self.values = values

    def all(self) -> list[Agent]:
        return self.values


class _ParticipantsResult:
    def __init__(self, values: list[Agent]) -> None:
        self.values = values

    def scalars(self) -> _Scalars:
        return _Scalars(self.values)


class _TransferSession:
    def __init__(self, participants: list[Agent]) -> None:
        self.participants = participants
        self.queries: list[object] = []
        self.added: list[object] = []
        self.committed = False

    async def execute(self, query: object) -> _ParticipantsResult:
        self.queries.append(query)
        return _ParticipantsResult(self.participants)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for value in self.added:
            if isinstance(value, Transaction):
                value.id = 1
                value.created_at = datetime.now(timezone.utc)

    async def commit(self) -> None:
        self.committed = True


def _agent(agent_id: UUID, name: str, balance: int) -> Agent:
    return Agent(
        id=agent_id,
        name=name,
        description=name,
        credits_balance=balance,
        messages_sent=0,
        messages_received=0,
        transactions_sent=0,
        transactions_received=0,
        is_active=True,
    )


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/transaction/send",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


def test_transfer_locks_participants_in_uuid_order_and_conserves_credits() -> None:
    high_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    low_id = UUID("00000000-0000-0000-0000-000000000001")
    sender = _agent(high_id, "Sender", 100)
    recipient = _agent(low_id, "Recipient", 20)
    session = _TransferSession([recipient, sender])

    result = asyncio.run(
        send_credits(
            TransactionSendRequest(to_agent_id=recipient.id, amount=25, note="test"),
            _request(),
            agent=sender,
            session=session,
        )
    )

    assert result.amount == 25
    assert sender.credits_balance == 75
    assert recipient.credits_balance == 45
    assert sender.credits_balance + recipient.credits_balance == 120
    assert sender.transactions_sent == 1
    assert recipient.transactions_received == 1
    assert session.committed is True

    query = session.queries[0]
    assert "ORDER BY agents.id" in str(query)
    assert list(query.compile().params.values()) == [[low_id, high_id]]


def test_opposing_transfer_queries_use_the_same_lock_order() -> None:
    low_id = UUID("00000000-0000-0000-0000-000000000001")
    high_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    async def _run(sender_id: UUID, recipient_id: UUID) -> list[UUID]:
        sender = _agent(sender_id, "Sender", 100)
        recipient = _agent(recipient_id, "Recipient", 100)
        participants = sorted([sender, recipient], key=lambda value: value.id.int)
        session = _TransferSession(participants)
        await send_credits(
            TransactionSendRequest(to_agent_id=recipient_id, amount=1),
            _request(),
            agent=sender,
            session=session,
        )
        return list(session.queries[0].compile().params.values())[0]

    forward_order = asyncio.run(_run(low_id, high_id))
    reverse_order = asyncio.run(_run(high_id, low_id))

    assert forward_order == [low_id, high_id]
    assert reverse_order == [low_id, high_id]
