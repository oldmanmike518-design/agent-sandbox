from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_log import EventLog


async def log_event(
    session: AsyncSession,
    *,
    event_type: str,
    agent_id: UUID | None,
    request: Request | None,
    payload: dict[str, Any] | None = None,
) -> None:
    ip = None
    user_agent = None
    if request is not None:
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    session.add(
        EventLog(
            event_type=event_type,
            agent_id=agent_id,
            ip=ip,
            user_agent=user_agent,
            payload=payload,
        )
    )
