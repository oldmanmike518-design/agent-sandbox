from __future__ import annotations

import uuid
from datetime import timedelta

from app.models.verification import VerificationObservation, VerificationRun
from app.services.verification.evaluators import evaluate_run
from app.utils.time import utc_now

BOOT = "boot-1"
T0 = utc_now()


def _run(**kwargs) -> VerificationRun:
    defaults = {
        "id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "status": "completed",
        "phase": "finalizable",
        "nonce": "nonce:aaa",
        "fresh_nonce": "nonce:fff",
        "nonce_message_id": 100,
        "replay_after_id": 99,
        "opened_at": T0,
        "deadline_at": T0 + timedelta(seconds=900),
        "fixture_message_ids": [101, 102, 103, 104, 105, 106],
        "boot_ids": [BOOT],
        "verifier_incidents": [],
        "verifier_fault": False,
        "run_metadata": {},
    }
    defaults.update(kwargs)
    return VerificationRun(**defaults)


def _obs(
    kind: str,
    payload: dict,
    *,
    seconds: float,
    boot: str = BOOT,
) -> VerificationObservation:
    observation = VerificationObservation(
        run_id=uuid.uuid4(),
        boot_id=boot,
        kind=kind,
        payload=payload,
    )
    observation.created_at = T0 + timedelta(seconds=seconds)
    observation.id = int(seconds * 1000) + 1
    return observation


def _compliant_observations() -> list[VerificationObservation]:
    observations = [
        _obs(
            "discovery",
            {"endpoint": "/agents", "partner_seen": True},
            seconds=1,
        ),
        _obs(
            "message_send",
            {
                "is_partner": True,
                "token_match": None,
                "message_id": 50,
            },
            seconds=2,
        ),
    ]
    now = 3.0
    for after_id, served, next_after in [
        (0, [100], 100),
        (100, [101, 102], 102),
        (102, [103, 104, 105, 106], 106),
    ]:
        observations.append(
            _obs(
                "inbox_poll",
                {
                    "after_id": after_id,
                    "served_partner_ids": served,
                    "next_after_id": next_after,
                },
                seconds=now,
            )
        )
        now += 1
    observations.append(
        _obs(
            "message_send",
            {
                "is_partner": True,
                "token_match": "nonce",
                "message_id": 51,
            },
            seconds=now,
        )
    )
    now += 1
    observations.append(
        _obs(
            "inbox_poll",
            {
                "after_id": 99,
                "served_partner_ids": [100],
                "next_after_id": 100,
            },
            seconds=now,
        )
    )
    now += 1
    observations.append(
        _obs(
            "inbox_poll",
            {
                "after_id": 106,
                "served_partner_ids": [107],
                "next_after_id": 107,
            },
            seconds=now,
        )
    )
    now += 1
    observations.append(
        _obs(
            "message_send",
            {
                "is_partner": True,
                "token_match": "fresh_nonce",
                "message_id": 52,
            },
            seconds=now,
        )
    )
    return observations


def _evaluate(observations, **run_kwargs):
    return evaluate_run(
        _run(**run_kwargs),
        observations,
        dead_lettered_slots=set(),
    )


def test_compliant_client_scores_eight_pass():
    results = _evaluate(_compliant_observations())
    assert {result["state"] for result in results.values()} == {"PASS"}
    assert len(results) == 8


def test_double_echo_fails_duplicate_suppression_only():
    observations = _compliant_observations()
    observations.append(
        _obs(
            "message_send",
            {
                "is_partner": True,
                "token_match": "nonce",
                "message_id": 53,
            },
            seconds=60,
        )
    )
    results = _evaluate(observations)
    assert results["duplicate_delivery_suppression"]["state"] == "FAIL"
    assert results["nonce_round_trip"]["state"] == "PASS"


def test_unreturned_cursor_fails_forward_cursor():
    observations = _compliant_observations()
    observations.append(
        _obs(
            "inbox_poll",
            {
                "after_id": 5,
                "served_partner_ids": [],
                "next_after_id": None,
            },
            seconds=61,
        )
    )
    assert (
        _evaluate(observations)["forward_cursor_correctness"]["state"]
        == "FAIL"
    )


def test_fixture_not_served_before_fresh_echo_is_not_observed():
    observations = [
        item
        for item in _compliant_observations()
        if not (
            item.kind == "inbox_poll"
            and 103 in (item.payload.get("served_partner_ids") or [])
        )
    ]
    result = _evaluate(observations)["edge_payload_recovery"]
    assert result["state"] == "NOT_OBSERVED"
    assert result["evidence"]["reason"] == "fixtures_not_all_served"


def test_incident_downgrades_possibly_verifier_caused_fail():
    observations = _compliant_observations()
    observations.append(
        _obs(
            "inbox_poll",
            {
                "after_id": 5,
                "served_partner_ids": [],
                "next_after_id": None,
            },
            seconds=61,
        )
    )
    results = _evaluate(
        observations,
        verifier_incidents=[
            {"path": "/message/inbox", "status": 500, "at": "t"}
        ],
    )
    result = results["forward_cursor_correctness"]
    assert result["state"] == "NOT_OBSERVED"
    assert result["evidence"]["reason"] == "verifier_incident"


def test_regression_to_previously_returned_cursor_fails():
    observations = _compliant_observations()
    observations.append(
        _obs(
            "inbox_poll",
            {
                "after_id": 102,
                "served_partner_ids": [],
                "next_after_id": 106,
            },
            seconds=61,
        )
    )
    assert (
        _evaluate(observations)["forward_cursor_correctness"]["state"]
        == "FAIL"
    )


def test_empty_page_repoll_of_same_cursor_is_legal():
    observations = _compliant_observations()
    observations.extend(
        [
            _obs(
                "inbox_poll",
                {
                    "after_id": 107,
                    "served_partner_ids": [],
                    "next_after_id": None,
                },
                seconds=61,
            ),
            _obs(
                "inbox_poll",
                {
                    "after_id": 107,
                    "served_partner_ids": [108],
                    "next_after_id": 108,
                },
                seconds=62,
            ),
        ]
    )
    assert (
        _evaluate(observations)["forward_cursor_correctness"]["state"]
        == "PASS"
    )


def test_echo_only_client_does_not_pass_direct_message_send():
    observations = [
        item
        for item in _compliant_observations()
        if not (
            item.kind == "message_send"
            and item.payload.get("token_match") is None
        )
    ]
    assert (
        _evaluate(observations)["direct_message_send"]["state"]
        == "NOT_OBSERVED"
    )


def test_replay_without_nonce_leaves_duplicate_not_observed():
    observations = []
    for item in _compliant_observations():
        if (
            item.kind == "inbox_poll"
            and item.payload.get("after_id") == 99
        ):
            item.payload = {
                **item.payload,
                "served_partner_ids": [],
            }
        observations.append(item)
    assert (
        _evaluate(observations)["duplicate_delivery_suppression"]["state"]
        == "NOT_OBSERVED"
    )


def test_hot_loop_fails_polling_discipline():
    observations = _compliant_observations()
    for index in range(6):
        observations.append(
            _obs(
                "inbox_poll",
                {
                    "after_id": 107 + index,
                    "served_partner_ids": [],
                },
                seconds=62 + index * 0.01,
            )
        )
    assert _evaluate(observations)["polling_discipline"]["state"] == "FAIL"


def test_silence_yields_not_observed_never_fail():
    results = _evaluate([], phase="main")
    assert all(
        result["state"] == "NOT_OBSERVED"
        for result in results.values()
    )


def test_boot_change_degrades_polling_to_not_observed():
    result = _evaluate(
        _compliant_observations(),
        boot_ids=[BOOT, "boot-2"],
    )["polling_discipline"]
    assert result["state"] == "NOT_OBSERVED"
    assert result["evidence"]["reason"] == "verifier_restart"


def test_dead_lettered_nonce_degrades_dependents_to_not_observed():
    results = evaluate_run(
        _run(),
        [],
        dead_lettered_slots={"nonce"},
    )
    for check in (
        "inbox_consumption",
        "nonce_round_trip",
        "duplicate_delivery_suppression",
    ):
        assert results[check]["state"] == "NOT_OBSERVED"
        assert results[check]["evidence"]["reason"] == "verifier_fault"
