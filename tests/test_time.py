from __future__ import annotations

from datetime import timedelta

from app.utils.time import utc_now


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().utcoffset() == timedelta(0)
