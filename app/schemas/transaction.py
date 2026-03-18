from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionSendRequest(BaseModel):
    to_agent_id: UUID | None = None
    to_agent_name: str | None = None
    amount: int = Field(..., gt=0)
    note: str | None = Field(default=None, max_length=500)


class TransactionOut(BaseModel):
    id: int
    from_agent_id: UUID
    to_agent_id: UUID
    amount: int
    note: str | None
    created_at: datetime
