from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.models.verification import (
    VerificationOutboxAction,
    VerificationReport,
    VerificationReportPublication,
    VerificationRun,
)
from app.schemas.agent import AdminAgentActionResponse
from app.services.auth import require_admin_key
from app.services.events import log_event
from app.utils.time import utc_now


router = APIRouter(prefix="/admin")


async def _update_agent_credentials(
    *,
    agent_id: UUID,
    request: Request,
    session: AsyncSession,
    deactivate: bool,
) -> AdminAgentActionResponse:
    values: dict[str, object] = {
        "credential_version": Agent.credential_version + 1,
    }
    if deactivate:
        values["is_active"] = False

    statement = (
        update(Agent)
        .where(Agent.id == agent_id)
        .values(**values)
        .returning(Agent.is_active, Agent.credential_version)
    )
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    is_active, credential_version = row

    open_run = (
        await session.execute(
            select(VerificationRun).where(
                VerificationRun.agent_id == agent_id,
                VerificationRun.status == "open",
            )
        )
    ).scalar_one_or_none()
    if open_run is not None:
        open_run.status = "aborted"
        open_run.lifecycle_note = (
            "agent_deactivated"
            if deactivate
            else "credentials_revoked"
        )

    event_type = "admin_agent_deactivate" if deactivate else "admin_credential_revoke"
    await log_event(
        session,
        event_type=event_type,
        agent_id=agent_id,
        request=request,
        payload={"credential_version": credential_version},
    )
    await session.commit()
    return AdminAgentActionResponse(
        agent_id=agent_id,
        is_active=is_active,
        credential_version=credential_version,
    )


@router.post(
    "/agents/{agent_id}/revoke",
    response_model=AdminAgentActionResponse,
    dependencies=[Depends(require_admin_key)],
)
async def revoke_agent_credentials(
    agent_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await _update_agent_credentials(
        agent_id=agent_id,
        request=request,
        session=session,
        deactivate=False,
    )


@router.post(
    "/agents/{agent_id}/deactivate",
    response_model=AdminAgentActionResponse,
    dependencies=[Depends(require_admin_key)],
)
async def deactivate_agent(
    agent_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await _update_agent_credentials(
        agent_id=agent_id,
        request=request,
        session=session,
        deactivate=True,
    )


async def _admin_report_publication(
    session: AsyncSession, slug: str
) -> tuple[VerificationReport, VerificationReportPublication]:
    row = (
        await session.execute(
            select(
                VerificationReport,
                VerificationReportPublication,
            )
            .join(
                VerificationReportPublication,
                VerificationReportPublication.report_id
                == VerificationReport.id,
            )
            .where(VerificationReport.slug == slug)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return row[0], row[1]


@router.post(
    "/reports/{slug}/delist",
    dependencies=[Depends(require_admin_key)],
)
async def admin_delist_report(
    slug: str, session: AsyncSession = Depends(get_session)
):
    report, publication = await _admin_report_publication(session, slug)
    publication.listed = False
    publication.updated_at = utc_now()
    await log_event(
        session,
        event_type="admin_report_delist",
        agent_id=report.agent_id,
        request=None,
        payload={"slug": slug},
    )
    await session.commit()
    return {"slug": slug, "listed": False}


@router.post(
    "/reports/{slug}/disable",
    dependencies=[Depends(require_admin_key)],
)
async def admin_disable_report(
    slug: str, session: AsyncSession = Depends(get_session)
):
    report, publication = await _admin_report_publication(session, slug)
    publication.disabled = True
    publication.listed = False
    publication.updated_at = utc_now()
    await log_event(
        session,
        event_type="admin_report_disable",
        agent_id=report.agent_id,
        request=None,
        payload={"slug": slug},
    )
    await session.commit()
    return {"slug": slug, "disabled": True}


@router.get(
    "/verification/dead-letters",
    dependencies=[Depends(require_admin_key)],
)
async def admin_dead_letters(
    session: AsyncSession = Depends(get_session),
):
    rows = (
        (
            await session.execute(
                select(VerificationOutboxAction).where(
                    VerificationOutboxAction.dead_lettered.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": action.id,
                "run_id": str(action.run_id),
                "kind": action.kind,
                "attempts": action.attempt_count,
                "last_error": action.last_error,
                "created_at": action.created_at,
            }
            for action in rows
        ]
    }
