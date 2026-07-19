from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.message import Message
from app.services.system_agents import CONFORMANCE_AGENT_ID


class ConformanceDriver(Protocol):
    async def send_partner_message(
        self,
        session: AsyncSession,
        *,
        recipient_id: UUID,
        subject: str | None,
        content: str,
    ) -> int: ...


class InProcessConformanceDriver:
    async def send_partner_message(
        self,
        session: AsyncSession,
        *,
        recipient_id: UUID,
        subject: str | None,
        content: str,
    ) -> int:
        message = Message(
            sender_id=CONFORMANCE_AGENT_ID,
            recipient_id=recipient_id,
            is_broadcast=False,
            subject=subject,
            content=content,
        )
        session.add(message)
        recipient = (
            await session.execute(
                select(Agent).where(Agent.id == recipient_id)
            )
        ).scalar_one_or_none()
        if recipient is not None:
            recipient.messages_received += 1
        await session.flush()
        return message.id


driver: ConformanceDriver = InProcessConformanceDriver()
