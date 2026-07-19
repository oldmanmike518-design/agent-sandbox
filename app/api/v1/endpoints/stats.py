from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.models.message import Message
from app.models.transaction import Transaction
from app.schemas.stats import PublicStats

router = APIRouter()


@router.get("/stats", response_model=PublicStats)
async def stats(session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    agents_total = int(
        (
            await session.execute(
                select(func.count(Agent.id)).where(
                    Agent.is_active.is_(True),
                    Agent.system_operated.is_(False),
                )
            )
        ).scalar_one()
    )
    agents_active_24h = int(
        (
            await session.execute(
                select(func.count(Agent.id)).where(
                    Agent.is_active.is_(True),
                    Agent.system_operated.is_(False),
                    Agent.last_seen_at.is_not(None),
                    Agent.last_seen_at >= last_24h,
                )
            )
        ).scalar_one()
    )

    system_ids = (
        select(Agent.id)
        .where(Agent.system_operated.is_(True))
        .scalar_subquery()
    )
    messages_total = int(
        (
            await session.execute(
                select(func.count(Message.id)).where(
                    Message.sender_id.not_in(system_ids),
                    (Message.recipient_id.is_(None))
                    | (Message.recipient_id.not_in(system_ids)),
                )
            )
        ).scalar_one()
    )
    transactions_total = int((await session.execute(select(func.count(Transaction.id)))).scalar_one())

    credits_total_issued = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(Agent.credits_balance), 0)).where(
                    Agent.is_active.is_(True),
                    Agent.system_operated.is_(False),
                )
            )
        ).scalar_one()
    )

    return PublicStats(
        agents_total=agents_total,
        agents_active_24h=agents_active_24h,
        messages_total=messages_total,
        transactions_total=transactions_total,
        credits_total_issued=credits_total_issued,
    )
