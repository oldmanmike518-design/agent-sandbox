from __future__ import annotations

from app.services.verification.outbox import retry_delay_seconds


def test_retry_delay_is_bounded_exponential():
    assert retry_delay_seconds(1) == 2
    assert retry_delay_seconds(2) == 4
    assert retry_delay_seconds(3) == 8
    assert retry_delay_seconds(10) == 300
