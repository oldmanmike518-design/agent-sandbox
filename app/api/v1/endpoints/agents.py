from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.schemas.agent import AgentMe, AgentPublic
from app.services.auth import get_current_agent

router = APIRouter()


@router.get("/agents", response_model=list[AgentPublic])
async def list_agents(
    q: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    query = select(Agent).where(Agent.is_active.is_(True)).order_by(Agent.created_at.desc()).limit(limit).offset(offset)
    if q:
        query = (
            select(Agent)
            .where(Agent.is_active.is_(True))
            .where(func.lower(Agent.name).contains(q.lower()))
            .order_by(Agent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

    agents = (await session.execute(query)).scalars().all()
    return [
        AgentPublic(
            id=a.id,
            name=a.name,
            description=a.description,
            created_at=a.created_at,
            last_seen_at=a.last_seen_at,
        )
        for a in agents
    ]


@router.get("/agents/me", response_model=AgentMe)
async def me(
    agent: Agent = Depends(get_current_agent),
):
    return AgentMe(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        created_at=agent.created_at,
        last_seen_at=agent.last_seen_at,
        credits_balance=agent.credits_balance,
        messages_sent=agent.messages_sent,
        messages_received=agent.messages_received,
        transactions_sent=agent.transactions_sent,
        transactions_received=agent.transactions_received,
    )
