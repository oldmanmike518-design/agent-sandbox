"""Initial schema

Revision ID: 0001_init
Revises: 
Create Date: 2026-03-03

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credits_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transactions_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transactions_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_agents_name", "agents", ["name"], unique=True)
    # Case-insensitive uniqueness
    op.create_index("ux_agents_name_lower", "agents", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("is_broadcast", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("subject", sa.String(length=140), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_id", "messages", ["id"], unique=False)
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"], unique=False)
    op.create_index("ix_messages_recipient_id", "messages", ["recipient_id"], unique=False)
    op.create_index("ix_messages_is_broadcast", "messages", ["is_broadcast"], unique=False)
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("from_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("to_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transactions_from_agent_id", "transactions", ["from_agent_id"], unique=False)
    op.create_index("ix_transactions_to_agent_id", "transactions", ["to_agent_id"], unique=False)
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"], unique=False)

    op.create_table(
        "event_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_event_logs_event_type", "event_logs", ["event_type"], unique=False)
    op.create_index("ix_event_logs_agent_id", "event_logs", ["agent_id"], unique=False)
    op.create_index("ix_event_logs_created_at", "event_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("event_logs")
    op.drop_table("transactions")
    op.drop_table("messages")
    op.drop_index("ux_agents_name_lower", table_name="agents")
    op.drop_table("agents")
