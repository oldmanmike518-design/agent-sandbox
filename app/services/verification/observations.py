from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.runtime import BOOT_ID
from app.models.verification import VerificationObservation, VerificationRun
from app.utils.time import utc_now


def cap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    encoded_bytes = len(json.dumps(payload, default=str).encode("utf-8"))
    if encoded_bytes <= settings.VERIFY_OBSERVATION_MAX_BYTES:
        return payload
    return {"truncated": True, "original_bytes": encoded_bytes}


def note_boot_id(run: VerificationRun, boot_id: str) -> None:
    if boot_id not in run.boot_ids:
        run.boot_ids = [*run.boot_ids, boot_id]
        flag_modified(run, "boot_ids")


async def get_active_run(
    session: AsyncSession, agent_id: UUID
) -> VerificationRun | None:
    result = await session.execute(
        select(VerificationRun).where(
            VerificationRun.agent_id == agent_id,
            VerificationRun.status == "open",
        )
    )
    return result.scalar_one_or_none()


async def record_observation(
    session: AsyncSession,
    run: VerificationRun,
    *,
    kind: str,
    payload: dict[str, Any],
) -> VerificationObservation | None:
    """Insert evidence in the caller's transaction. Caller commits."""
    count = (
        await session.execute(
            select(func.count(VerificationObservation.id)).where(
                VerificationObservation.run_id == run.id
            )
        )
    ).scalar_one()
    if count >= settings.VERIFY_MAX_OBSERVATIONS_PER_RUN:
        run.run_metadata = {**run.run_metadata, "observation_cap_hit": True}
        flag_modified(run, "run_metadata")
        return None

    note_boot_id(run, BOOT_ID)
    observation = VerificationObservation(
        run_id=run.id,
        boot_id=BOOT_ID,
        kind=kind,
        payload=cap_payload(payload),
    )
    session.add(observation)
    return observation


async def purge_expired_observations(
    session: AsyncSession, *, now: datetime | None = None
) -> int:
    cutoff = (now or utc_now()) - timedelta(
        days=settings.EVENT_LOG_RETENTION_DAYS
    )
    result = await session.execute(
        delete(VerificationObservation).where(
            VerificationObservation.created_at < cutoff
        )
    )
    await session.commit()
    return result.rowcount or 0
