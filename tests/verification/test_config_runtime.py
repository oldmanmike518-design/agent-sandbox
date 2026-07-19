from __future__ import annotations

import uuid

from app.core.config import settings


def test_verification_settings_defaults():
    assert settings.VERIFY_RUN_DEADLINE_SECONDS_DEFAULT == 900
    assert settings.VERIFY_RUN_DEADLINE_SECONDS_MAX == 1800
    assert settings.VERIFY_RUNS_PER_AGENT_PER_DAY == 10
    assert settings.VERIFY_RUNS_PER_IP_PER_DAY == 20
    assert settings.VERIFY_RUNS_GLOBAL_PER_DAY == 200
    assert settings.VERIFY_MAX_OBSERVATIONS_PER_RUN == 500
    assert settings.VERIFY_MAX_OUTBOX_PER_RUN == 20
    assert settings.VERIFY_POLL_FLOOR_MS == 250
    assert settings.VERIFY_STALL_CEILING_SECONDS == 300
    assert settings.VERIFY_OBSERVATION_MAX_BYTES == 4096
    assert settings.VERIFY_OUTBOX_MAX_ATTEMPTS == 5
    assert settings.VERIFY_OUTBOX_LEASE_SECONDS == 60


def test_boot_id_is_stable_uuid():
    from app.core import runtime

    first = runtime.BOOT_ID
    second = runtime.BOOT_ID
    assert first == second
    uuid.UUID(first)  # raises if not a valid UUID string
