from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.models.agent import Agent
from app.models.message import Message
from app.schemas.message import InboxResponse, MessageOut, MessageSendRequest
from app.services.auth import get_current_agent
from app.services.events import log_event
from app.services.rate_limit import enforce_message_limit

router = APIRouter(prefix="/message")


@router.post("/send", response_model=MessageOut)
async def send_message(
    body: MessageSendRequest,
    request: Request,
    response: Response,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")
    if len(content) > settings.MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=400, detail=f"Message too long (max {settings.MAX_MESSAGE_CHARS})")

    # Rate limit per agent
    allowed, remaining, reset_seconds = await enforce_message_limit(agent.id, session)
    response.headers["X-RateLimit-Limit"] = str(settings.MESSAGE_LIMIT_PER_HOUR)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_seconds)

    if not allowed:
        raise HTTPException(status_code=429, detail="Message rate limit exceeded")

    recipient_id = body.to_agent_id
    if recipient_id is None and body.to_agent_name:
        q = select(Agent).where(func.lower(Agent.name) == body.to_agent_name.lower())
        recipient = (await session.execute(q)).scalar_one_or_none()
        if recipient is None:
            raise HTTPException(status_code=404, detail="Recipient agent not found")
        recipient_id = recipient.id

    is_broadcast = recipient_id is None
    if not is_broadcast:
        if recipient_id == agent.id:
            raise HTTPException(status_code=400, detail="Cannot message yourself")

        q = select(Agent).where(Agent.id == recipient_id, Agent.is_active.is_(True))
        recipient = (await session.execute(q)).scalar_one_or_none()
        if recipient is None:
            raise HTTPException(status_code=404, detail="Recipient agent not found")

    msg = Message(
        sender_id=agent.id,
        recipient_id=recipient_id,
        is_broadcast=is_broadcast,
        subject=body.subject.strip() if body.subject else None,
        content=content,
    )
    session.add(msg)

    # Update counters
    agent.messages_sent += 1
    if not is_broadcast:
        recipient.messages_received += 1  # type: ignore[name-defined]

    await log_event(
        session,
        event_type="message_send",
        agent_id=agent.id,
        request=request,
        payload={
            "recipient_id": str(recipient_id) if recipient_id else None,
            "is_broadcast": is_broadcast,
        },
    )

    await session.flush()
    await session.commit()

    return MessageOut(
        id=msg.id,
        sender_id=msg.sender_id,
        recipient_id=msg.recipient_id,
        is_broadcast=msg.is_broadcast,
        subject=msg.subject,
        content=msg.content,
        created_at=msg.created_at,
    )


@router.get("/inbox", response_model=InboxResponse)
async def inbox(
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
):
    q = select(Message).where(
        (Message.recipient_id == agent.id) | (Message.is_broadcast.is_(True))
    ).order_by(Message.id.desc()).limit(limit)

    if before_id is not None:
        q = q.where(Message.id < before_id)

    rows = (await session.execute(q)).scalars().all()
    items = [
        MessageOut(
            id=m.id,
            sender_id=m.sender_id,
            recipient_id=m.recipient_id,
            is_broadcast=m.is_broadcast,
            subject=m.subject,
            content=m.content,
            created_at=m.created_at,
        )
        for m in rows
    ]

    next_before = items[-1].id if len(items) == limit else None
    return InboxResponse(items=items, next_before_id=next_before)
