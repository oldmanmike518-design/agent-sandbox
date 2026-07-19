#!/usr/bin/env python3
"""Delete event_log rows older than EVENT_LOG_RETENTION_DAYS.

Run this on a schedule (cron, a Render cron job, or a periodic task) to enforce
the retention policy documented in PRIVACY.md.

    ENV=production DATABASE_URL=... PYTHONPATH=. python scripts/purge_old_events.py
"""
from __future__ import annotations

import asyncio

from app.db.session import AsyncSessionLocal
from app.services.events import purge_expired_events
from app.services.verification.observations import (
    purge_expired_observations,
)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        deleted = await purge_expired_events(session)
        print(f"Deleted {deleted} expired event_log row(s)")
    async with AsyncSessionLocal() as session:
        deleted_observations = await purge_expired_observations(session)
        print(
            "Deleted "
            f"{deleted_observations} expired "
            "verification_observation row(s)"
        )


if __name__ == "__main__":
    asyncio.run(main())
