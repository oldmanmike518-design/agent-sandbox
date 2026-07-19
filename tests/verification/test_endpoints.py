from __future__ import annotations

import html
import uuid
from datetime import timedelta

from app.api.v1.endpoints.reports import (
    badge_payload,
    render_report_html,
)
from app.models.verification import VerificationReport
from app.utils.time import utc_now


def _report(**kwargs) -> VerificationReport:
    defaults = {
        "id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "slug": "s" * 16,
        "profile": "rest-interop",
        "spec_version": "0.1-draft",
        "spec_sha256": "a" * 64,
        "engine_commit": "abc123",
        "report_schema_version": 1,
        "agent_name_snapshot": '<script>alert("x")</script>',
        "framework_self_reported": "CrewAI",
        "results": {
            "capability_discovery": {
                "state": "PASS",
                "evidence": {},
            }
        },
        "passed": 8,
        "failed": 0,
        "not_observed": 0,
        "complete": True,
        "verifier_fault": False,
        "verified_at": utc_now(),
        "created_at": utc_now(),
    }
    defaults.update(kwargs)
    return VerificationReport(**defaults)


def test_badge_complete_clean_is_green_with_score_and_date():
    payload = badge_payload(_report())
    assert payload["schemaVersion"] == 1
    assert payload["label"] == "interop rest-interop v0.1-draft"
    assert payload["message"].startswith("8/8 · ")
    assert payload["color"] == "brightgreen"
    assert payload["cacheSeconds"] == 3600


def test_badge_incomplete_is_grey_without_score():
    payload = badge_payload(
        _report(complete=False, not_observed=2, passed=6)
    )
    assert payload["message"] == "incomplete"
    assert payload["color"] == "lightgrey"


def test_badge_stale_is_grey_at_91_days_but_not_at_89():
    assert (
        badge_payload(
            _report(verified_at=utc_now() - timedelta(days=91))
        )["color"]
        == "lightgrey"
    )
    assert (
        badge_payload(
            _report(verified_at=utc_now() - timedelta(days=89))
        )["color"]
        == "brightgreen"
    )


def test_report_html_escapes_agent_name():
    page = render_report_html(_report())
    assert "<script>" not in page
    assert html.escape('<script>alert("x")</script>') in page
