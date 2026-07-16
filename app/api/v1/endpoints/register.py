from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.models.agent import Agent
from app.schemas.agent import AgentMe, RegisterRequest, RegisterResponse
from app.services.abuse_control import consume_registration_limit
from app.services.auth import create_jwt
from app.services.events import log_event
from app.services.tip_jar import build_tip_jar
from app.utils.validation import validate_agent_name

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
async def register_agent(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    limit_decision = await consume_registration_limit(request, session)
    response.headers.update(limit_decision.headers)
    if not limit_decision.allowed:
        raise HTTPException(
            status_code=429,
            detail="Registration rate limit exceeded",
            headers=limit_decision.headers,
        )

    try:
        name = validate_agent_name(body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    description = body.description.strip()
    if len(description) > settings.MAX_DESCRIPTION_CHARS:
        raise HTTPException(status_code=400, detail=f"Description too long (max {settings.MAX_DESCRIPTION_CHARS})")

    # Case-insensitive uniqueness
    exists_q = select(Agent).where(func.lower(Agent.name) == name.lower())
    existing = (await session.execute(exists_q)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Agent name already taken")

    agent = Agent(name=name, description=description, credits_balance=settings.STARTING_CREDITS)
    session.add(agent)
    try:
        await session.flush()  # assigns agent.id
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Agent name already taken")

    token = create_jwt(agent.id, agent.name, agent.credential_version)

    await log_event(
        session,
        event_type="register",
        agent_id=agent.id,
        request=request,
        payload={"name": agent.name},
    )

    await session.commit()

    agent_me = AgentMe(
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

    return RegisterResponse(agent=agent_me, token=token, tip_jar=build_tip_jar())
