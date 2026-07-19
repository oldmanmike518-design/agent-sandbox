from __future__ import annotations

import uuid
from datetime import timedelta

from app.models.verification import VerificationObservation, VerificationRun
from app.services.verification.runs import build_instructions, next_phase
from app.utils.time import utc_now


def _run(**kwargs) -> VerificationRun:
    defaults = {
        "id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "status": "open",
        "phase": "main",
        "profile": "rest-interop",
        "spec_version": "0.1-draft",
        "instructions_schema_version": 1,
        "nonce": "nonce:aaa",
        "fresh_nonce": None,
        "nonce_message_id": 100,
        "replay_after_id": 99,
        "opened_at": utc_now(),
        "deadline_at": utc_now() + timedelta(seconds=900),
        "fixture_message_ids": [],
        "boot_ids": [],
        "verifier_incidents": [],
        "run_metadata": {},
    }
    defaults.update(kwargs)
    return VerificationRun(**defaults)


def _obs(kind: str, payload: dict) -> VerificationObservation:
    return VerificationObservation(
        run_id=uuid.uuid4(),
        boot_id="b",
        kind=kind,
        payload=payload,
    )


def test_phase_main_advances_on_nonce_echo():
    run = _run(phase="main")
    echo = _obs(
        "message_send",
        {"is_partner": True, "token_match": "nonce"},
    )
    assert next_phase(run, echo) == "await_overlap"


def test_phase_await_overlap_advances_on_replay_poll_serving_nonce():
    run = _run(phase="await_overlap")
    replay = _obs(
        "inbox_poll",
        {"after_id": 99, "served_partner_ids": [100]},
    )
    assert next_phase(run, replay) == "await_fresh"


def test_phase_await_overlap_ignores_replay_poll_without_nonce():
    run = _run(phase="await_overlap")
    replay = _obs(
        "inbox_poll",
        {"after_id": 99, "served_partner_ids": []},
    )
    assert next_phase(run, replay) == "await_overlap"


def test_phase_await_fresh_advances_on_fresh_echo():
    run = _run(phase="await_fresh", fresh_nonce="nonce:fff")
    echo = _obs(
        "message_send",
        {"is_partner": True, "token_match": "fresh_nonce"},
    )
    assert next_phase(run, echo) == "finalizable"


def test_phase_ignores_unrelated_observations():
    run = _run(phase="main")
    poll = _obs(
        "inbox_poll",
        {"after_id": 0, "served_partner_ids": []},
    )
    assert next_phase(run, poll) == "main"


def test_instructions_contract():
    run = _run()
    payload = build_instructions(
        run, partner_name="InteropConformanceAgent"
    )
    assert payload["instructions_schema_version"] == 1
    assert payload["profile"] == "rest-interop"
    assert payload["state"]["phase"] == "main"
    assert payload["state"]["replay_after_id"] == 99
    assert {step["check"] for step in payload["steps"]} == {
        "capability_discovery",
        "direct_message_send",
        "inbox_consumption",
        "nonce_round_trip",
        "forward_cursor_correctness",
        "duplicate_delivery_suppression",
        "edge_payload_recovery",
        "polling_discipline",
    }
