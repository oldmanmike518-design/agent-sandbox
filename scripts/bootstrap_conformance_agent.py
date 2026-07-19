#!/usr/bin/env python3
"""Idempotently create the system conformance partner."""

from __future__ import annotations

import asyncio

from app.db.session import AsyncSessionLocal
from app.services.system_agents import (
    CONFORMANCE_AGENT_NAME,
    ensure_conformance_agent,
)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await ensure_conformance_agent(session)
        print(f"Bootstrap ensured: {CONFORMANCE_AGENT_NAME}")


if __name__ == "__main__":
    asyncio.run(main())
