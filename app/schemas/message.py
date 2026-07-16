from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MessageSendRequest(BaseModel):
    to_agent_id: UUID | None = None
    to_agent_name: str | None = None
    subject: str | None = Field(default=None, max_length=140)
    content: str = Field(..., min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: int
    sender_id: UUID
    recipient_id: UUID | None
    is_broadcast: bool
    subject: str | None
    content: str
    created_at: datetime


class InboxResponse(BaseModel):
    items: list[MessageOut]
    next_before_id: int | None
    next_after_id: int | None = None
