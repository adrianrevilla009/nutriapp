"""create nutrition-assistant-service tables

Revision ID: 0001
Revises:
Create Date: 2026-09-07

Additive-only (database-migrations SKILL.md's expand/contract pattern) --
this is the first migration for this service, so there is nothing to
expand from; every table here is new."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_entry_history",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.String(length=2000), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_food_entry_history_user_id", "food_entry_history", ["user_id"])

    op.create_table(
        "water_intake_history",
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.String(length=2000), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_water_intake_history_user_id", "water_intake_history", ["user_id"])

    op.create_table(
        "nutrition_value_history",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(length=16), primary_key=True),
        sa.Column("reference_id", sa.String(length=128), primary_key=True),
        sa.Column("on_date", sa.Date(), nullable=True),
        sa.Column("summary", sa.String(length=2000), nullable=False),
    )
    op.create_index("ix_nutrition_value_history_user_id", "nutrition_value_history", ["user_id"])

    op.create_table(
        "nutrition_target_history",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("summary", sa.String(length=2000), nullable=False),
    )

    op.create_table(
        "analytics_signal_history",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signal", sa.String(length=64), primary_key=True),
        sa.Column("summary", sa.String(length=2000), nullable=False),
        sa.Column("disclaimer", sa.String(length=2000), nullable=False),
    )
    op.create_index("ix_analytics_signal_history_user_id", "analytics_signal_history", ["user_id"])

    op.create_table(
        "entitlement_cache",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entitled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    for table_name in (
        "processed_diary_events",
        "processed_nutrition_calculation_events",
        "processed_analytics_events",
    ):
        op.create_table(
            table_name,
            sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        )

    op.create_table(
        "chat_audit_log",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(length=4000), nullable=False),
        sa.Column("retrieved_record_ids", postgresql.JSONB(), nullable=False),
        sa.Column("prompt_template_version", sa.String(length=16), nullable=False),
        sa.Column("had_sufficient_context", sa.Boolean(), nullable=False),
        sa.Column("disclaimer_included", sa.Boolean(), nullable=False),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_audit_log_user_id", "chat_audit_log", ["user_id"])

    op.create_table(
        "outbox",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unpublished", "outbox", ["published_at"])


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_index("ix_chat_audit_log_user_id", table_name="chat_audit_log")
    op.drop_table("chat_audit_log")
    op.drop_table("processed_analytics_events")
    op.drop_table("processed_nutrition_calculation_events")
    op.drop_table("processed_diary_events")
    op.drop_table("entitlement_cache")
    op.drop_index("ix_analytics_signal_history_user_id", table_name="analytics_signal_history")
    op.drop_table("analytics_signal_history")
    op.drop_table("nutrition_target_history")
    op.drop_index("ix_nutrition_value_history_user_id", table_name="nutrition_value_history")
    op.drop_table("nutrition_value_history")
    op.drop_index("ix_water_intake_history_user_id", table_name="water_intake_history")
    op.drop_table("water_intake_history")
    op.drop_index("ix_food_entry_history_user_id", table_name="food_entry_history")
    op.drop_table("food_entry_history")
