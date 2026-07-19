from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models.verification import (
    VerificationOutboxAction,
    VerificationRun,
)
from app.services.verification.driver import driver
from app.utils.time import utc_now

RETRY_CAP_SECONDS = 300


def retry_delay_seconds(attempt: int) -> int:
    return min(2**attempt, RETRY_CAP_SECONDS)


async def enqueue(
    session: AsyncSession,
    *,
    run: VerificationRun,
    kind: str,
    payload: dict[str, Any],
    idempotency_key: str,
    required: bool = True,
) -> VerificationOutboxAction | None:
    """Enqueue in the caller's transaction; the caller commits."""
    count = (
        await session.execute(
            select(func.count(VerificationOutboxAction.id)).where(
                VerificationOutboxAction.run_id == run.id
            )
        )
    ).scalar_one()
    if count >= settings.VERIFY_MAX_OUTBOX_PER_RUN:
        run.run_metadata = {**run.run_metadata, "outbox_cap_hit": True}
        flag_modified(run, "run_metadata")
        return None
    action = VerificationOutboxAction(
        run_id=run.id,
        kind=kind,
        payload=payload,
        idempotency_key=idempotency_key,
        required=required,
        available_at=utc_now(),
    )
    session.add(action)
    return action


async def drain_pending(session: AsyncSession, run_id: UUID) -> None:
    """Drain available actions after their enqueueing transaction commits."""
    while True:
        now = utc_now()
        claim_query = (
            select(VerificationOutboxAction)
            .where(
                VerificationOutboxAction.run_id == run_id,
                VerificationOutboxAction.completed_at.is_(None),
                VerificationOutboxAction.dead_lettered.is_(False),
                VerificationOutboxAction.available_at <= now,
                (
                    VerificationOutboxAction.claim_expires_at.is_(None)
                    | (VerificationOutboxAction.claim_expires_at < now)
                ),
            )
            .order_by(VerificationOutboxAction.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        action = (
            await session.execute(claim_query)
        ).scalar_one_or_none()
        if action is None:
            await session.commit()
            return

        action.attempt_count += 1
        action.claimed_at = now
        action.claim_expires_at = now + timedelta(
            seconds=settings.VERIFY_OUTBOX_LEASE_SECONDS
        )
        await session.commit()

        try:
            await _execute(session, action)
            action.completed_at = utc_now()
            action.last_error = None
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            action = await session.get(VerificationOutboxAction, action.id)
            if action is None:
                return
            action.last_error = str(exc)[:500]
            if (
                action.attempt_count
                >= settings.VERIFY_OUTBOX_MAX_ATTEMPTS
            ):
                action.dead_lettered = True
            else:
                action.available_at = utc_now() + timedelta(
                    seconds=retry_delay_seconds(action.attempt_count)
                )
            action.claim_expires_at = None
            await session.commit()
            return


async def _execute(
    session: AsyncSession, action: VerificationOutboxAction
) -> None:
    if action.kind != "partner_message":
        raise ValueError(f"Unknown outbox action kind: {action.kind}")

    message_id = await driver.send_partner_message(
        session,
        recipient_id=UUID(action.payload["recipient_id"]),
        subject=action.payload.get("subject"),
        content=action.payload["content"],
    )
    run = await session.get(VerificationRun, action.run_id)
    if run is None:
        raise RuntimeError("Verification run missing for outbox action")
    slot = action.payload.get("slot")
    if slot == "nonce":
        run.nonce_message_id = message_id
        run.replay_after_id = message_id - 1
    elif slot == "fixture":
        run.fixture_message_ids = [*run.fixture_message_ids, message_id]
        flag_modified(run, "fixture_message_ids")
    elif slot == "fresh_nonce":
        run.run_metadata = {
            **run.run_metadata,
            "fresh_nonce_message_id": message_id,
        }
        flag_modified(run, "run_metadata")
