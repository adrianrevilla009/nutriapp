"""Create pending_push_dispatch table.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate. Holds
one-shot non-transactional push sends deferred past a quiet-hours window
(domain/entities/pending_push_dispatch.py); deliberately a new table
rather than a reuse/overload of reminder_schedule's periodic shape.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_push_dispatch",
        sa.Column("dispatch_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("template_name", sa.String(64), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("earliest_dispatch_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
    )
    op.create_index("ix_pending_push_dispatch_user_id", "pending_push_dispatch", ["user_id"])
    op.create_index(
        "ix_pending_push_dispatch_status_earliest_dispatch_at",
        "pending_push_dispatch",
        ["status", "earliest_dispatch_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pending_push_dispatch_status_earliest_dispatch_at",
        table_name="pending_push_dispatch",
    )
    op.drop_index("ix_pending_push_dispatch_user_id", table_name="pending_push_dispatch")
    op.drop_table("pending_push_dispatch")
