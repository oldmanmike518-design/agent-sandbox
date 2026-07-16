"""Add revocable agent credential versions.

Revision ID: 0003_agent_credential_version
Revises: 0002_rate_limit_buckets
Create Date: 2026-07-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_agent_credential_version"
down_revision = "0002_rate_limit_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "credential_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "credential_version")
