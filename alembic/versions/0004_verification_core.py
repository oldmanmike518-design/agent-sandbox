"""Verification core: runs, reports, observations, outbox, system agents.

Revision ID: 0004_verification_core
Revises: 0003_agent_credential_version
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0004_verification_core"
down_revision = "0003_agent_credential_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("system_operated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "verification_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("profile", sa.String(32), nullable=False, server_default="rest-interop"),
        sa.Column("spec_version", sa.String(16), nullable=False, server_default="0.1-draft"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("phase", sa.String(24), nullable=False, server_default="main"),
        sa.Column("instructions_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("fresh_nonce", sa.String(64), nullable=True),
        sa.Column("nonce_message_id", sa.BigInteger(), nullable=True),
        sa.Column("replay_after_id", sa.BigInteger(), nullable=True),
        sa.Column("fixture_message_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("boot_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("verifier_incidents", JSONB(), nullable=False, server_default="[]"),
        sa.Column("verifier_fault", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("budget_refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lifecycle_note", sa.String(64), nullable=True),
        sa.Column("run_metadata", JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_verification_runs_agent_id", "verification_runs", ["agent_id"])
    op.create_index("ix_verification_runs_agent_status", "verification_runs", ["agent_id", "status"])
    op.create_index(
        "uq_verification_runs_one_open",
        "verification_runs",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.create_table(
        "verification_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("verification_runs.id"), nullable=False, unique=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("slug", sa.String(32), nullable=False),
        sa.Column("profile", sa.String(32), nullable=False),
        sa.Column("spec_version", sa.String(16), nullable=False),
        sa.Column("spec_sha256", sa.String(64), nullable=False),
        sa.Column("engine_commit", sa.String(64), nullable=False),
        sa.Column("report_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("agent_name_snapshot", sa.String(64), nullable=False),
        sa.Column("framework_self_reported", sa.String(128), nullable=True),
        sa.Column("results", JSONB(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("not_observed", sa.Integer(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("verifier_fault", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_reports_agent_id", "verification_reports", ["agent_id"])
    op.create_index("ix_verification_reports_slug", "verification_reports", ["slug"], unique=True)

    op.create_table(
        "verification_report_publication",
        sa.Column("report_id", UUID(as_uuid=True), sa.ForeignKey("verification_reports.id"), primary_key=True),
        sa.Column("listed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "verification_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("verification_runs.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("boot_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_verification_observations_run_id", "verification_observations", ["run_id"])
    op.create_index(
        "ix_verification_observations_run_created",
        "verification_observations",
        ["run_id", "created_at"],
    )

    op.create_table(
        "verification_outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("verification_runs.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_outbox_run_id", "verification_outbox", ["run_id"])
    op.create_index(
        "ix_verification_outbox_pending",
        "verification_outbox",
        ["available_at"],
        postgresql_where=sa.text("completed_at IS NULL AND dead_lettered = false"),
    )


def downgrade() -> None:
    op.drop_table("verification_report_publication")
    op.drop_table("verification_outbox")
    op.drop_table("verification_observations")
    op.drop_table("verification_reports")
    op.drop_table("verification_runs")
    op.drop_column("agents", "system_operated")
