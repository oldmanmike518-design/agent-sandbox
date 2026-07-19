from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.verification import (
    VerificationObservation,
    VerificationOutboxAction,
    VerificationReport,
    VerificationReportPublication,
    VerificationRun,
)
from app.services.abuse_control import refund_verification_limit
from app.services.verification.evaluators import CHECK_IDS, evaluate_run
from app.services.verification.runs import touch_run
from app.services.verification.spec import (
    PROFILE_ID,
    REPORT_SCHEMA_VERSION,
    SPEC_VERSION,
    engine_commit,
    spec_sha256,
)
from app.utils.time import utc_now


async def finalize_run(
    session: AsyncSession, run_id: UUID, agent: Agent
) -> VerificationReport:
    """Finalize once under a row lock and return the immutable report."""
    run = (
        await session.execute(
            select(VerificationRun)
            .where(VerificationRun.id == run_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if run is None or run.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Run not found")

    existing = (
        await session.execute(
            select(VerificationReport).where(
                VerificationReport.run_id == run.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await session.commit()
        return existing

    await touch_run(session, run, agent)
    if run.status == "open":
        run.status = "completed"
    run.finalized_at = utc_now()

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
    dead_lettered = (
        (
            await session.execute(
                select(VerificationOutboxAction).where(
                    VerificationOutboxAction.run_id == run.id,
                    VerificationOutboxAction.dead_lettered.is_(True),
                    VerificationOutboxAction.required.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    dead_slots = {
        action.payload.get("slot")
        for action in dead_lettered
        if action.payload.get("slot")
    }
    if dead_slots:
        run.verifier_fault = True

    results = evaluate_run(
        run,
        list(observations),
        dead_lettered_slots=dead_slots,
    )
    states = [results[check]["state"] for check in CHECK_IDS]
    passed = states.count("PASS")
    failed = states.count("FAIL")
    not_observed = states.count("NOT_OBSERVED")
    complete = (
        run.status == "completed"
        and not_observed == 0
        and not run.verifier_fault
    )

    report = VerificationReport(
        run_id=run.id,
        agent_id=agent.id,
        slug=secrets.token_urlsafe(12),
        profile=PROFILE_ID,
        spec_version=SPEC_VERSION,
        spec_sha256=spec_sha256(),
        engine_commit=engine_commit(),
        report_schema_version=REPORT_SCHEMA_VERSION,
        agent_name_snapshot=agent.name,
        framework_self_reported=run.run_metadata.get(
            "framework_self_reported"
        ),
        results=results,
        passed=passed,
        failed=failed,
        not_observed=not_observed,
        complete=complete,
        verifier_fault=run.verifier_fault,
        verified_at=run.finalized_at,
    )
    session.add(report)
    await session.flush()
    session.add(VerificationReportPublication(report_id=report.id))
    if run.verifier_fault and run.budget_refunded_at is None:
        bucket_windows = run.run_metadata.get("budget_buckets") or []
        if bucket_windows:
            await refund_verification_limit(session, bucket_windows)
        run.budget_refunded_at = utc_now()
    await session.commit()
    return report
