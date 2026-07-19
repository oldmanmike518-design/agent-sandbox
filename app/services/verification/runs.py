from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.agent import Agent
from app.models.verification import VerificationObservation, VerificationRun
from app.services.abuse_control import (
    consume_verification_limit,
    refund_verification_limit,
)
from app.services.system_agents import (
    CONFORMANCE_AGENT_ID,
    CONFORMANCE_AGENT_NAME,
)
from app.services.verification.fixtures import (
    EDGE_FIXTURES,
    make_nonce,
    nonce_message_content,
)
from app.services.verification.outbox import drain_pending, enqueue
from app.utils.time import utc_now


def next_phase(
    run: VerificationRun, observation: VerificationObservation
) -> str:
    kind, payload = observation.kind, observation.payload
    if run.phase == "main":
        if (
            kind == "message_send"
            and payload.get("is_partner")
            and payload.get("token_match") == "nonce"
        ):
            return "await_overlap"
    elif run.phase == "await_overlap":
        if (
            kind == "inbox_poll"
            and payload.get("after_id") == run.replay_after_id
            and run.nonce_message_id
            in (payload.get("served_partner_ids") or [])
        ):
            return "await_fresh"
    elif run.phase == "await_fresh":
        if (
            kind == "message_send"
            and payload.get("is_partner")
            and payload.get("token_match") == "fresh_nonce"
        ):
            return "finalizable"
    return run.phase


async def advance_phase_on_observation(
    session: AsyncSession,
    run: VerificationRun,
    observation: VerificationObservation | None = None,
) -> bool:
    if observation is None:
        return False
    new_phase = next_phase(run, observation)
    if new_phase == run.phase:
        return False
    run.phase = new_phase
    if new_phase == "await_fresh":
        run.fresh_nonce = make_nonce()
        await enqueue(
            session,
            run=run,
            kind="partner_message",
            payload={
                "recipient_id": str(run.agent_id),
                "subject": "interop fresh nonce",
                "content": nonce_message_content(run.fresh_nonce),
                "slot": "fresh_nonce",
            },
            idempotency_key=f"{run.id}:fresh_nonce",
        )
        return True
    return False


async def touch_run(
    session: AsyncSession, run: VerificationRun, agent: Agent
) -> None:
    if run.status != "open":
        return
    if not agent.is_active:
        run.status = "aborted"
        run.lifecycle_note = "agent_deactivated"
        return
    if utc_now() > run.deadline_at:
        run.status = "expired"


def build_instructions(
    run: VerificationRun, *, partner_name: str
) -> dict[str, Any]:
    return {
        "instructions_schema_version": run.instructions_schema_version,
        "profile": run.profile,
        "spec_version": run.spec_version,
        "run_id": str(run.id),
        "deadline_at": run.deadline_at.isoformat(),
        "partner": {
            "id": str(CONFORMANCE_AGENT_ID),
            "name": partner_name,
        },
        "steps": [
            {
                "check": "capability_discovery",
                "action": (
                    "GET /agents with your Authorization header and locate "
                    "the partner by name."
                ),
            },
            {
                "check": "direct_message_send",
                "action": (
                    "POST /message/send a direct message to the partner "
                    "(any subject/content)."
                ),
            },
            {
                "check": "inbox_consumption",
                "action": (
                    "Poll GET /message/inbox?after_id=<cursor> forward until "
                    "you receive the partner message containing a token "
                    "starting 'nonce:'."
                ),
            },
            {
                "check": "nonce_round_trip",
                "action": (
                    "Reply to the partner with a message whose content "
                    "contains that exact token."
                ),
            },
            {
                "check": "duplicate_delivery_suppression",
                "action": (
                    "After replying, poll once with after_id equal to "
                    "state.replay_after_id (re-serves the nonce). Do NOT "
                    "reply to it again."
                ),
            },
            {
                "check": "edge_payload_recovery",
                "action": (
                    "Keep polling forward. Edge-case messages arrive; "
                    "continue operating. A fresh 'nonce:' token will arrive "
                    "— reply echoing it."
                ),
            },
            {
                "check": "forward_cursor_correctness",
                "action": (
                    "Always advance after_id using next_after_id, except the "
                    "single instructed replay."
                ),
            },
            {
                "check": "polling_discipline",
                "action": (
                    "Poll at a sane cadence: at least 250 ms apart, no gap "
                    "over 5 minutes."
                ),
            },
        ],
        "state": {
            "phase": run.phase,
            "replay_after_id": run.replay_after_id,
            "fresh_nonce_pending": run.phase == "await_fresh",
        },
    }


async def open_run(
    session: AsyncSession,
    request: Request,
    agent: Agent,
    *,
    deadline_seconds: int | None,
    framework: str | None,
) -> VerificationRun:
    if agent.system_operated:
        raise HTTPException(
            status_code=403, detail="System agents cannot be verified"
        )

    existing = (
        await session.execute(
            select(VerificationRun).where(
                VerificationRun.agent_id == agent.id,
                VerificationRun.status == "open",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="An open verification run already exists",
        )

    day_ago = utc_now() - timedelta(days=1)
    agent_runs_today = (
        await session.execute(
            select(func.count(VerificationRun.id)).where(
                VerificationRun.agent_id == agent.id,
                VerificationRun.opened_at >= day_ago,
                VerificationRun.verifier_fault.is_(False),
            )
        )
    ).scalar_one()
    if agent_runs_today >= settings.VERIFY_RUNS_PER_AGENT_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail="Daily verification run limit reached",
        )

    seconds = (
        deadline_seconds
        or settings.VERIFY_RUN_DEADLINE_SECONDS_DEFAULT
    )
    seconds = min(seconds, settings.VERIFY_RUN_DEADLINE_SECONDS_MAX)
    run = VerificationRun(
        agent_id=agent.id,
        nonce=make_nonce(),
        opened_at=utc_now(),
        deadline_at=utc_now() + timedelta(seconds=seconds),
        run_metadata={
            "registration_auth": True,
            "framework_self_reported": framework,
        },
    )
    session.add(run)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="An open verification run already exists",
        )

    decision = await consume_verification_limit(request)
    if not decision.allowed:
        await session.rollback()
        raise HTTPException(
            status_code=429,
            detail="Verification rate limit exceeded",
            headers=decision.headers,
        )

    try:
        run.run_metadata = {
            **run.run_metadata,
            "budget_buckets": decision.bucket_windows,
        }
        flag_modified(run, "run_metadata")

        await enqueue(
            session,
            run=run,
            kind="partner_message",
            payload={
                "recipient_id": str(agent.id),
                "subject": "interop nonce",
                "content": nonce_message_content(run.nonce),
                "slot": "nonce",
            },
            idempotency_key=f"{run.id}:nonce",
        )
        for fixture in EDGE_FIXTURES:
            await enqueue(
                session,
                run=run,
                kind="partner_message",
                payload={
                    "recipient_id": str(agent.id),
                    "subject": fixture["subject"],
                    "content": fixture["content"],
                    "slot": "fixture",
                },
                idempotency_key=(
                    f"{run.id}:fixture:{fixture['fixture_id']}"
                ),
            )
        await session.commit()
    except Exception:
        await session.rollback()
        try:
            async with AsyncSessionLocal() as refund_session:
                await refund_verification_limit(
                    refund_session, decision.bucket_windows
                )
                await refund_session.commit()
        except Exception:  # noqa: BLE001
            pass
        raise
    await drain_pending(session, run.id)
    await session.refresh(run)
    return run


__all__ = [
    "CONFORMANCE_AGENT_NAME",
    "advance_phase_on_observation",
    "build_instructions",
    "next_phase",
    "open_run",
    "touch_run",
]
