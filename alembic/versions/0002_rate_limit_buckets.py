"""Add atomic abuse-control buckets.

Revision ID: 0002_rate_limit_buckets
Revises: 0001_init
Create Date: 2026-07-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_rate_limit_buckets"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("bucket_key", sa.String(length=160), primary_key=True),
        sa.Column("count", sa.BigInteger(), nullable=False),
        sa.Column("window_ends_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_rate_limit_buckets_window_ends_at",
        "rate_limit_buckets",
        ["window_ends_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rate_limit_buckets_window_ends_at",
        table_name="rate_limit_buckets",
    )
    op.drop_table("rate_limit_buckets")
