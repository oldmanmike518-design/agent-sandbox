from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.models.verification import VerificationObservation, VerificationRun

CHECK_IDS = [
    "capability_discovery",
    "direct_message_send",
    "inbox_consumption",
    "nonce_round_trip",
    "forward_cursor_correctness",
    "duplicate_delivery_suppression",
    "edge_payload_recovery",
    "polling_discipline",
]

_DEAD_LETTER_DEPENDENTS = {
    "nonce": {
        "inbox_consumption",
        "nonce_round_trip",
        "duplicate_delivery_suppression",
    },
    "fixture": {"edge_payload_recovery"},
    "fresh_nonce": {"edge_payload_recovery"},
}

_INCIDENT_PATH_DEPENDENTS = {
    "/message/inbox": {
        "inbox_consumption",
        "forward_cursor_correctness",
        "duplicate_delivery_suppression",
        "polling_discipline",
    },
    "/message/send": {
        "direct_message_send",
        "nonce_round_trip",
        "edge_payload_recovery",
    },
    "/agents": {"capability_discovery"},
}


def _result(state: str, **evidence: Any) -> dict[str, Any]:
    return {"state": state, "evidence": evidence}


def evaluate_run(
    run: VerificationRun,
    observations: list[VerificationObservation],
    *,
    dead_lettered_slots: set[str],
) -> dict[str, dict[str, Any]]:
    obs = sorted(observations, key=lambda item: (item.created_at, item.id))
    sends = [
        item
        for item in obs
        if item.kind == "message_send"
        and item.payload.get("is_partner")
    ]
    polls = [item for item in obs if item.kind == "inbox_poll"]
    discoveries = [item for item in obs if item.kind == "discovery"]
    nonce_echoes = [
        item
        for item in sends
        if item.payload.get("token_match") == "nonce"
    ]
    fresh_echoes = [
        item
        for item in sends
        if item.payload.get("token_match") == "fresh_nonce"
    ]

    results: dict[str, dict[str, Any]] = {}
    results["capability_discovery"] = (
        _result("PASS", observations=len(discoveries))
        if any(item.payload.get("partner_seen") for item in discoveries)
        else _result("NOT_OBSERVED")
    )

    plain_sends = [
        item
        for item in sends
        if item.payload.get("token_match") is None
    ]
    if not plain_sends:
        results["direct_message_send"] = _result("NOT_OBSERVED")
    else:
        first_plain = plain_sends[0]
        first_echo = next(iter(nonce_echoes), None)
        if first_echo is not None and (
            first_plain.created_at,
            first_plain.id,
        ) > (first_echo.created_at, first_echo.id):
            results["direct_message_send"] = _result(
                "NOT_OBSERVED", reason="sent_after_echo"
            )
        else:
            results["direct_message_send"] = _result(
                "PASS", sends=len(plain_sends)
            )

    served_nonce = any(
        run.nonce_message_id
        in (poll.payload.get("served_partner_ids") or [])
        for poll in polls
    )
    results["inbox_consumption"] = (
        _result("PASS") if served_nonce else _result("NOT_OBSERVED")
    )
    results["nonce_round_trip"] = (
        _result("PASS", echoes=len(nonce_echoes))
        if nonce_echoes
        else _result("NOT_OBSERVED")
    )

    after_polls = [
        poll
        for poll in polls
        if poll.payload.get("after_id") is not None
    ]
    if len(after_polls) < 2:
        results["forward_cursor_correctness"] = _result("NOT_OBSERVED")
    else:
        expected, violations, replay_used = 0, 0, False
        for poll in after_polls:
            after_id = poll.payload["after_id"]
            if (
                after_id == run.replay_after_id
                and not replay_used
                and after_id != expected
            ):
                replay_used = True
                continue
            if after_id != expected:
                violations += 1
            next_after = poll.payload.get("next_after_id")
            if next_after is not None:
                expected = next_after
        results["forward_cursor_correctness"] = (
            _result("FAIL", violations=violations)
            if violations
            else _result("PASS")
        )

    replay_polls = [
        poll
        for poll in polls
        if poll.payload.get("after_id") == run.replay_after_id
        and run.nonce_message_id
        in (poll.payload.get("served_partner_ids") or [])
    ]
    if not replay_polls or not nonce_echoes:
        results["duplicate_delivery_suppression"] = _result(
            "NOT_OBSERVED"
        )
    elif len(nonce_echoes) == 1:
        results["duplicate_delivery_suppression"] = _result("PASS")
    else:
        results["duplicate_delivery_suppression"] = _result(
            "FAIL", echoes=len(nonce_echoes)
        )

    if run.fixture_message_ids and fresh_echoes:
        first_fresh = fresh_echoes[0]
        served_before_echo: set[int] = set()
        for poll in polls:
            if (poll.created_at, poll.id) < (
                first_fresh.created_at,
                first_fresh.id,
            ):
                served_before_echo.update(
                    poll.payload.get("served_partner_ids") or []
                )
        if set(run.fixture_message_ids) <= served_before_echo:
            results["edge_payload_recovery"] = _result("PASS")
        else:
            results["edge_payload_recovery"] = _result(
                "NOT_OBSERVED",
                reason="fixtures_not_all_served",
            )
    else:
        results["edge_payload_recovery"] = _result("NOT_OBSERVED")

    if len(run.boot_ids) > 1:
        results["polling_discipline"] = _result(
            "NOT_OBSERVED", reason="verifier_restart"
        )
    elif len(polls) < 3:
        results["polling_discipline"] = _result("NOT_OBSERVED")
    else:
        floor = settings.VERIFY_POLL_FLOOR_MS / 1000.0
        ceiling = settings.VERIFY_STALL_CEILING_SECONDS
        gaps = [
            (second.created_at - first.created_at).total_seconds()
            for first, second in zip(polls, polls[1:])
        ]
        floor_violations = sum(gap < floor for gap in gaps)
        stall = any(gap > ceiling for gap in gaps)
        if stall or floor_violations > 3:
            results["polling_discipline"] = _result(
                "FAIL",
                floor_violations=floor_violations,
                stalled=stall,
            )
        else:
            results["polling_discipline"] = _result(
                "PASS", polls=len(polls)
            )

    for slot in dead_lettered_slots:
        for check in _DEAD_LETTER_DEPENDENTS.get(slot, set()):
            results[check] = _result(
                "NOT_OBSERVED", reason="verifier_fault"
            )

    for incident in run.verifier_incidents or []:
        path = str(incident.get("path", ""))
        if path.startswith("/v1/"):
            path = path[3:]
        for check in _INCIDENT_PATH_DEPENDENTS.get(path, set()):
            if results[check]["state"] == "FAIL":
                results[check] = _result(
                    "NOT_OBSERVED", reason="verifier_incident"
                )

    return results
