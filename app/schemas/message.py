from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MessageSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_agent_id: UUID | None = None
    to_agent_name: str | None = None
    subject: str | None = Field(default=None, max_length=140)
    content: str = Field(..., min_length=1, max_length=2000)

    @model_validator(mode="after")
    def require_unambiguous_recipient(self) -> Self:
        if self.to_agent_id is not None and self.to_agent_name is not None:
            raise ValueError("Use either to_agent_id or to_agent_name, not both")
        return self


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
