from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

CONFORMANCE_AGENT_ID = uuid.UUID("00000000-0000-4000-a000-4e5245495459")
CONFORMANCE_AGENT_NAME = "InteropConformanceAgent"
CONFORMANCE_AGENT_DESCRIPTION = (
    "System-operated conformance partner for Interop verification runs. "
    "Not a real user. See /llms.txt and docs/INTEROP_SPEC.md."
)

_RESERVED_NAMES = {CONFORMANCE_AGENT_NAME.lower()}


def is_reserved_agent_name(name: str) -> bool:
    return name.strip().lower() in _RESERVED_NAMES


async def ensure_conformance_agent(session: AsyncSession) -> None:
    """Create the stable house partner, failing safely on identity conflicts."""
    statement = (
        insert(Agent)
        .values(
            id=CONFORMANCE_AGENT_ID,
            name=CONFORMANCE_AGENT_NAME,
            description=CONFORMANCE_AGENT_DESCRIPTION,
            credits_balance=0,
            system_operated=True,
        )
        .on_conflict_do_nothing(index_elements=[Agent.id])
    )
    await session.execute(statement)
    await session.commit()

    by_id = (
        await session.execute(select(Agent).where(Agent.id == CONFORMANCE_AGENT_ID))
    ).scalar_one_or_none()
    by_name = (
        await session.execute(
            select(Agent).where(
                func.lower(Agent.name) == CONFORMANCE_AGENT_NAME.lower()
            )
        )
    ).scalar_one_or_none()
    if (
        by_id is None
        or not by_id.system_operated
        or by_id.name != CONFORMANCE_AGENT_NAME
    ):
        raise RuntimeError(
            "Conformance-agent bootstrap conflict: the stable UUID row is "
            "missing or inconsistent"
        )
    if by_name is None or by_name.id != CONFORMANCE_AGENT_ID:
        raise RuntimeError(
            "Conformance-agent bootstrap conflict: the reserved name is held "
            "by another row"
        )
