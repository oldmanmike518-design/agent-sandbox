from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.time import utc_now

from app.db.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    credits_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    messages_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    messages_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    transactions_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transactions_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    credential_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    system_operated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
