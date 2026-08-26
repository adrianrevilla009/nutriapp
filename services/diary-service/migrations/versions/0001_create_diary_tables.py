"""Create diary-service tables: diary_events (single, aggregate_type-
discriminated event store), outbox, processed_inbound_events,
food_entries_view, water_intake_view, fasting_windows_view,
meal_plan_view, daily_summary_view.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate.

Revision ID: 0001
Revises:
Create Date: 2026-08-26

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
        "diary_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column("aggregate_type", sa.String(32), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("aggregate_sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_diary_events_aggregate_sequence",
        "diary_events",
        ["aggregate_type", "aggregate_id", "sequence"],
    )
    op.create_index(
        "ux_diary_events_aggregate_position",
        "diary_events",
        ["aggregate_type", "aggregate_id", "aggregate_sequence"],
        unique=True,
    )

    op.create_table(
        "outbox",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unpublished", "outbox", ["published_at"])

    op.create_table(
        "processed_inbound_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "food_entries_view",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("meal_slot", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calories_kcal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("protein_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carbs_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fat_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_food_entries_view_user_id", "food_entries_view", ["user_id"])
    op.create_index("ix_food_entries_view_occurred_at", "food_entries_view", ["occurred_at"])
    op.create_index(
        "ix_food_entries_view_user_occurred", "food_entries_view", ["user_id", "occurred_at"]
    )

    op.create_table(
        "water_intake_view",
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_ml", sa.Float(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_water_intake_view_user_id", "water_intake_view", ["user_id"])
    op.create_index("ix_water_intake_view_occurred_at", "water_intake_view", ["occurred_at"])
    op.create_index(
        "ix_water_intake_view_user_occurred", "water_intake_view", ["user_id", "occurred_at"]
    )

    op.create_table(
        "fasting_windows_view",
        sa.Column("window_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fasting_windows_view_user_id", "fasting_windows_view", ["user_id"])
    op.create_index(
        "ix_fasting_windows_view_user_started", "fasting_windows_view", ["user_id", "started_at"]
    )

    op.create_table(
        "meal_plan_view",
        sa.Column("plan_entry_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("meal_slot", sa.String(16), nullable=False),
        sa.Column("planned_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_meal_plan_view_user_id", "meal_plan_view", ["user_id"])
    op.create_index("ix_meal_plan_view_planned_for", "meal_plan_view", ["planned_for"])
    op.create_index("ix_meal_plan_view_user_planned", "meal_plan_view", ["user_id", "planned_for"])

    op.create_table(
        "daily_summary_view",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("summary_date", sa.String(10), primary_key=True),
        sa.Column("total_calories_kcal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_protein_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_carbs_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_fat_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_water_ml", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fasting_windows_ended", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("daily_summary_view")
    op.drop_index("ix_meal_plan_view_user_planned", table_name="meal_plan_view")
    op.drop_index("ix_meal_plan_view_planned_for", table_name="meal_plan_view")
    op.drop_index("ix_meal_plan_view_user_id", table_name="meal_plan_view")
    op.drop_table("meal_plan_view")
    op.drop_index("ix_fasting_windows_view_user_started", table_name="fasting_windows_view")
    op.drop_index("ix_fasting_windows_view_user_id", table_name="fasting_windows_view")
    op.drop_table("fasting_windows_view")
    op.drop_index("ix_water_intake_view_user_occurred", table_name="water_intake_view")
    op.drop_index("ix_water_intake_view_occurred_at", table_name="water_intake_view")
    op.drop_index("ix_water_intake_view_user_id", table_name="water_intake_view")
    op.drop_table("water_intake_view")
    op.drop_index("ix_food_entries_view_user_occurred", table_name="food_entries_view")
    op.drop_index("ix_food_entries_view_occurred_at", table_name="food_entries_view")
    op.drop_index("ix_food_entries_view_user_id", table_name="food_entries_view")
    op.drop_table("food_entries_view")
    op.drop_table("processed_inbound_events")
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ux_diary_events_aggregate_position", table_name="diary_events")
    op.drop_index("ix_diary_events_aggregate_sequence", table_name="diary_events")
    op.drop_table("diary_events")
