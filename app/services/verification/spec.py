from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path

PROFILE_ID = "rest-interop"
SPEC_VERSION = "0.1-draft"
REPORT_SCHEMA_VERSION = 1
INSTRUCTIONS_SCHEMA_VERSION = 1

_SPEC_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "INTEROP_SPEC.md"
)


@lru_cache(maxsize=1)
def spec_sha256() -> str:
    return hashlib.sha256(_SPEC_PATH.read_bytes()).hexdigest()


def engine_commit() -> str:
    return (
        os.environ.get("RENDER_GIT_COMMIT")
        or os.environ.get("GIT_COMMIT")
        or "unknown"
    )
