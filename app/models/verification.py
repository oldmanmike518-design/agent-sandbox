from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.time import utc_now


class VerificationRun(Base):
    __tablename__ = "verification_runs"
    __table_args__ = (
        Index(
            "uq_verification_runs_one_open",
            "agent_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_verification_runs_agent_status", "agent_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), index=True, nullable=False)
    profile: Mapped[str] = mapped_column(String(32), default="rest-interop", nullable=False)
    spec_version: Mapped[str] = mapped_column(String(16), default="0.1-draft", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)  # open|completed|expired|aborted
    phase: Mapped[str] = mapped_column(String(24), default="main", nullable=False)  # main|await_overlap|await_fresh|finalizable
    instructions_schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    fresh_nonce: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nonce_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    replay_after_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fixture_message_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    boot_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    verifier_incidents: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    verifier_fault: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Refund idempotency guard: set exactly once, under the finalize row lock.
    budget_refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_note: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class VerificationReport(Base):
    __tablename__ = "verification_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification_runs.id"), unique=True, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    profile: Mapped[str] = mapped_column(String(32), nullable=False)
    spec_version: Mapped[str] = mapped_column(String(16), nullable=False)
    spec_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    report_schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    agent_name_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    framework_self_reported: Mapped[str | None] = mapped_column(String(128), nullable=True)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    passed: Mapped[int] = mapped_column(Integer, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, nullable=False)
    not_observed: Mapped[int] = mapped_column(Integer, nullable=False)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    verifier_fault: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class VerificationReportPublication(Base):
    """Mutable publication state, deliberately a SEPARATE table so the report
    row itself has no update path at all (immutable evidence vs. publication)."""

    __tablename__ = "verification_report_publication"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("verification_reports.id"), primary_key=True
    )
    listed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class VerificationObservation(Base):
    __tablename__ = "verification_observations"
    __table_args__ = (Index("ix_verification_observations_run_created", "run_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification_runs.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    boot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class VerificationOutboxAction(Base):
    __tablename__ = "verification_outbox"
    __table_args__ = (
        Index(
            "ix_verification_outbox_pending",
            "available_at",
            postgresql_where=text("completed_at IS NULL AND dead_lettered = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification_runs.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
