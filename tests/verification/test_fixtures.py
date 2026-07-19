from __future__ import annotations

from app.core.config import settings
from app.services.verification.fixtures import (
    EDGE_FIXTURES,
    make_nonce,
    nonce_message_content,
)


def test_edge_fixture_shape_and_ids():
    ids = [fixture["fixture_id"] for fixture in EDGE_FIXTURES]
    assert ids == [
        "empty-subject",
        "max-length",
        "unicode-rtl",
        "json-shaped",
        "markdown-fences",
        "injection-shaped",
    ]
    for fixture in EDGE_FIXTURES:
        assert set(fixture) == {"fixture_id", "subject", "content"}
        assert len(fixture["content"]) <= settings.MAX_MESSAGE_CHARS


def test_max_length_fixture_is_exactly_max():
    fixture = next(
        fixture
        for fixture in EDGE_FIXTURES
        if fixture["fixture_id"] == "max-length"
    )
    assert len(fixture["content"]) == settings.MAX_MESSAGE_CHARS


def test_nonce_format_and_uniqueness():
    first, second = make_nonce(), make_nonce()
    assert first != second
    assert first.startswith("nonce:") and len(first) <= 64
    assert first in nonce_message_content(first)
