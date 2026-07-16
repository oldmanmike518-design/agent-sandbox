from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.event_log import EventLog
from app.utils.time import utc_now


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


def retention_cutoff(now: datetime | None = None) -> datetime:
    """Timestamp before which event logs (including IP/user-agent) are expired."""
    reference = now or utc_now()
    return reference - timedelta(days=settings.EVENT_LOG_RETENTION_DAYS)


async def purge_expired_events(
    session: AsyncSession, *, now: datetime | None = None
) -> int:
    """Delete event logs older than the configured retention window.

    Returns the number of rows removed. Intended to be run on a schedule.
    """
    cutoff = retention_cutoff(now)
    result = await session.execute(
        delete(EventLog).where(EventLog.created_at < cutoff)
    )
    await session.commit()
    return result.rowcount or 0
