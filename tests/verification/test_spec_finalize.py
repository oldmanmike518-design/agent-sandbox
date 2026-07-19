from __future__ import annotations

import re
from pathlib import Path

from app.services.verification.evaluators import CHECK_IDS
from app.services.verification.spec import (
    PROFILE_ID,
    REPORT_SCHEMA_VERSION,
    SPEC_VERSION,
    engine_commit,
    spec_sha256,
)


def test_constants():
    assert PROFILE_ID == "rest-interop"
    assert SPEC_VERSION == "0.1-draft"
    assert REPORT_SCHEMA_VERSION == 1


def test_spec_file_exists_and_names_every_check():
    text = Path("docs/INTEROP_SPEC.md").read_text(encoding="utf-8")
    for check_id in CHECK_IDS:
        assert check_id in text
    assert "PROVISIONAL" in text


def test_spec_hash_is_hex_sha256():
    assert re.fullmatch(r"[0-9a-f]{64}", spec_sha256())


def test_engine_commit_returns_string():
    assert isinstance(engine_commit(), str) and engine_commit()
