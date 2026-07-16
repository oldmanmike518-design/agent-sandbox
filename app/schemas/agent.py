from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=32)
    description: str = Field(..., min_length=1, max_length=500)


class AgentPublic(BaseModel):
    id: UUID
    name: str
    description: str
    created_at: datetime
    last_seen_at: datetime | None


class AgentMe(AgentPublic):
    credits_balance: int
    messages_sent: int
    messages_received: int
    transactions_sent: int
    transactions_received: int


class RegisterResponse(BaseModel):
    agent: AgentMe
    token: str
    tip_jar: dict


class TokenResponse(BaseModel):
    token: str


class AdminAgentActionResponse(BaseModel):
    agent_id: UUID
    is_active: bool
    credential_version: int
