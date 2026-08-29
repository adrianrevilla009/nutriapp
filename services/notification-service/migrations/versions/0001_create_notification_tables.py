"""Create notification-service tables: reminder_schedule,
processed_notifications, delivery_log, suppression_list,
notification_preferences.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate. New
service, no existing schema to preserve compatibility with
(implementation plan section 7).

Revision ID: 0001
Revises:
Create Date: 2026-08-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminder_schedule",
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("source_aggregate_id", sa.String(64), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("relevance_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("next_eligible_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "source_aggregate_id", "category", name="uq_reminder_schedule_source_category"
        ),
    )
    op.create_index("ix_reminder_schedule_user_id", "reminder_schedule", ["user_id"])
    op.create_index("ix_reminder_schedule_status_due_at", "reminder_schedule", ["status", "due_at"])

    op.create_table(
        "processed_notifications",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel", sa.String(16), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "delivery_log",
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("template_name", sa.String(64), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_reason", sa.String(1024), nullable=True),
    )
    op.create_index("ix_delivery_log_user_id", "delivery_log", ["user_id"])

    op.create_table(
        "suppression_list",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel", sa.String(16), primary_key=True),
        sa.Column("address_or_device", sa.String(320), primary_key=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(32), primary_key=True),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("quiet_hours_start", sa.Time(), nullable=False),
        sa.Column("quiet_hours_end", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("suppression_list")
    op.drop_index("ix_delivery_log_user_id", table_name="delivery_log")
    op.drop_table("delivery_log")
    op.drop_table("processed_notifications")
    op.drop_index("ix_reminder_schedule_status_due_at", table_name="reminder_schedule")
    op.drop_index("ix_reminder_schedule_user_id", table_name="reminder_schedule")
    op.drop_table("reminder_schedule")
