from __future__ import annotations

from datetime import datetime, timedelta, timezone

import app.core.config as config_module
from app.services.events import retention_cutoff


def test_retention_cutoff_subtracts_configured_days() -> None:
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    expected_days = config_module.settings.EVENT_LOG_RETENTION_DAYS

    cutoff = retention_cutoff(now)

    assert cutoff == now - timedelta(days=expected_days)
    assert cutoff.tzinfo is not None


def test_retention_cutoff_honors_overridden_window() -> None:
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    original = config_module.settings.EVENT_LOG_RETENTION_DAYS
    config_module.settings.EVENT_LOG_RETENTION_DAYS = 30
    try:
        cutoff = retention_cutoff(now)
    finally:
        config_module.settings.EVENT_LOG_RETENTION_DAYS = original

    assert cutoff == now - timedelta(days=30)
