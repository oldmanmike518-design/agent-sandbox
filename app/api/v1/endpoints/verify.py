from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.models.verification import (
    VerificationObservation,
    VerificationReport,
    VerificationRun,
)
from app.schemas.verification import VerifyOpenRequest
from app.services.auth import get_current_agent
from app.services.system_agents import CONFORMANCE_AGENT_NAME
from app.services.verification.evaluators import evaluate_run
from app.services.verification.finalize import finalize_run
from app.services.verification.outbox import drain_pending
from app.services.verification.runs import (
    build_instructions,
    open_run,
    touch_run,
)

router = APIRouter(prefix="/verify")


async def _owned_run(
    session: AsyncSession, run_id: UUID, agent: Agent
) -> VerificationRun:
    run = (
        await session.execute(
            select(VerificationRun).where(
                VerificationRun.id == run_id
            )
        )
    ).scalar_one_or_none()
    if run is None or run.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("", status_code=201)
async def open_verification(
    body: VerifyOpenRequest,
    request: Request,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    run = await open_run(
        session,
        request,
        agent,
        deadline_seconds=body.deadline_seconds,
        framework=body.framework,
    )
    return {
        "run_id": str(run.id),
        "status": run.status,
        "deadline_at": run.deadline_at,
        "instructions": build_instructions(
            run, partner_name=CONFORMANCE_AGENT_NAME
        ),
    }


@router.get("/{run_id}")
async def run_status(
    run_id: UUID,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    run = await _owned_run(session, run_id, agent)
    await touch_run(session, run, agent)
    observations = (
        (
            await session.execute(
                select(VerificationObservation)
                .where(VerificationObservation.run_id == run.id)
                .order_by(
                    VerificationObservation.created_at,
                    VerificationObservation.id,
                )
            )
        )
        .scalars()
        .all()
    )
    progress = evaluate_run(
        run,
        list(observations),
        dead_lettered_slots=set(),
    )
    report_slug = (
        await session.execute(
            select(VerificationReport.slug).where(
                VerificationReport.run_id == run.id
            )
        )
    ).scalar_one_or_none()
    await session.commit()
    await drain_pending(session, run.id)
    return {
        "run_id": str(run.id),
        "status": run.status,
        "phase": run.phase,
        "deadline_at": run.deadline_at,
        "instructions": build_instructions(
            run, partner_name=CONFORMANCE_AGENT_NAME
        ),
        "progress": {
            check: result["state"]
            for check, result in progress.items()
        },
        "report_slug": report_slug,
    }


@router.post("/{run_id}/finalize")
async def finalize(
    run_id: UUID,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    report = await finalize_run(session, run_id, agent)
    return {
        "report_slug": report.slug,
        "complete": report.complete,
        "passed": report.passed,
        "failed": report.failed,
        "not_observed": report.not_observed,
        "verifier_fault": report.verifier_fault,
    }
