from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionOut, TransactionSendRequest
from app.services.auth import get_current_agent
from app.services.events import log_event
from app.services.tip_jar import build_tip_jar

router = APIRouter(prefix="/transaction")


@router.post("/send", response_model=TransactionOut)
async def send_credits(
    body: TransactionSendRequest,
    request: Request,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be > 0")

    recipient_id = body.to_agent_id
    if recipient_id is None and body.to_agent_name:
        q = select(Agent).where(func.lower(Agent.name) == body.to_agent_name.lower())
        recipient = (await session.execute(q)).scalar_one_or_none()
        if recipient is None:
            raise HTTPException(status_code=404, detail="Recipient agent not found")
        recipient_id = recipient.id

    if recipient_id is None:
        raise HTTPException(status_code=400, detail="Provide to_agent_id or to_agent_name")
    if recipient_id == agent.id:
        raise HTTPException(status_code=400, detail="Cannot send credits to yourself")

    # Lock both rows in a deterministic order so opposing transfers cannot
    # deadlock by each holding its sender while waiting for its recipient.
    participant_ids = sorted((agent.id, recipient_id), key=lambda value: value.int)
    participants_q = (
        select(Agent)
        .where(Agent.id.in_(participant_ids))
        .order_by(Agent.id)
        .with_for_update()
    )
    participants = (await session.execute(participants_q)).scalars().all()
    participants_by_id = {participant.id: participant for participant in participants}

    sender = participants_by_id.get(agent.id)
    recipient = participants_by_id.get(recipient_id)
    if sender is None:
        raise HTTPException(status_code=401, detail="Sender agent not found")
    if recipient is None or not recipient.is_active:
        raise HTTPException(status_code=404, detail="Recipient agent not found")

    if sender.credits_balance < body.amount:
        raise HTTPException(status_code=400, detail="Insufficient credits")

    sender.credits_balance -= body.amount
    recipient.credits_balance += body.amount

    sender.transactions_sent += 1
    recipient.transactions_received += 1

    tx = Transaction(
        from_agent_id=sender.id,
        to_agent_id=recipient.id,
        amount=body.amount,
        note=body.note.strip() if body.note else None,
    )
    session.add(tx)

    await log_event(
        session,
        event_type="transaction_send",
        agent_id=sender.id,
        request=request,
        payload={"to": str(recipient.id), "amount": body.amount},
    )

    await session.flush()
    await session.commit()

    return TransactionOut(
        id=tx.id,
        from_agent_id=tx.from_agent_id,
        to_agent_id=tx.to_agent_id,
        amount=tx.amount,
        note=tx.note,
        created_at=tx.created_at,
    )


@router.post("/tip")
async def tip_post():
    return build_tip_jar()


@router.get("/tip")
async def tip_get():
    return build_tip_jar()
