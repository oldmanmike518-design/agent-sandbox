from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.schemas.agent import AgentMe, AgentPublic, TokenResponse
from app.services.auth import create_jwt, get_current_agent
from app.services.events import log_event

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


@router.post("/agents/me/rotate-token", response_model=TokenResponse)
async def rotate_token(
    request: Request,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        update(Agent)
        .where(
            Agent.id == agent.id,
            Agent.is_active.is_(True),
            Agent.credential_version == agent.credential_version,
        )
        .values(credential_version=Agent.credential_version + 1)
        .returning(Agent.name, Agent.credential_version)
    )
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=401,
            detail="Token has been revoked or already rotated",
        )
    agent_name, credential_version = row

    await log_event(
        session,
        event_type="credential_rotate",
        agent_id=agent.id,
        request=request,
        payload={"credential_version": credential_version},
    )
    await session.commit()
    return TokenResponse(
        token=create_jwt(agent.id, agent_name, credential_version),
    )
