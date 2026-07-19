from __future__ import annotations

import json
import uuid

from app.core.config import settings
from app.models.verification import VerificationRun
from app.services.verification.observations import cap_payload, note_boot_id


def _run() -> VerificationRun:
    return VerificationRun(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        nonce="nonce:abc",
        boot_ids=[],
        run_metadata={},
    )


def test_cap_payload_passes_small_payloads_through():
    payload = {"after_id": 5, "served_partner_ids": [1, 2]}
    assert cap_payload(payload) == payload


def test_cap_payload_truncates_by_utf8_bytes_not_characters():
    payload = {"blob": "🌍" * settings.VERIFY_OBSERVATION_MAX_BYTES}
    capped = cap_payload(payload)
    assert capped["truncated"] is True
    assert (
        len(json.dumps(capped).encode("utf-8"))
        <= settings.VERIFY_OBSERVATION_MAX_BYTES
    )


def test_note_boot_id_appends_new_boot_only_once():
    run = _run()
    note_boot_id(run, "boot-1")
    note_boot_id(run, "boot-1")
    note_boot_id(run, "boot-2")
    assert run.boot_ids == ["boot-1", "boot-2"]


def test_observation_retention_uses_event_log_window():
    from datetime import timedelta

    from app.services.events import retention_cutoff
    from app.utils.time import utc_now

    now = utc_now()
    cutoff = now - timedelta(days=settings.EVENT_LOG_RETENTION_DAYS)
    assert (
        abs((retention_cutoff(now) - cutoff).total_seconds()) < 1
    )
