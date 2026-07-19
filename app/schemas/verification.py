from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VerifyOpenRequest(BaseModel):
    deadline_seconds: int | None = Field(default=None, ge=60, le=3600)
    framework: str | None = Field(default=None, max_length=128)


class VerifyStatusResponse(BaseModel):
    run_id: str
    status: str
    phase: str
    deadline_at: datetime
    instructions: dict[str, Any]
    progress: dict[str, Any]
    report_slug: str | None = None


class ListingUpdateResponse(BaseModel):
    slug: str
    listed: bool
