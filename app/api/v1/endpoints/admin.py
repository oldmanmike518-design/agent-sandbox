from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.schemas.agent import AdminAgentActionResponse
from app.services.auth import require_admin_key
from app.services.events import log_event


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
