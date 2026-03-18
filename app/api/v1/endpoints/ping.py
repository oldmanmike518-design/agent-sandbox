from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.services.auth import get_current_agent
from app.services.events import log_event

router = APIRouter()


@router.post("/ping")
async def ping(
    request: Request,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    agent.last_seen_at = datetime.now(timezone.utc)
    await log_event(session, event_type="ping", agent_id=agent.id, request=request)
    await session.commit()
    return {"status": "ok", "server_time": datetime.now(timezone.utc).isoformat()}
