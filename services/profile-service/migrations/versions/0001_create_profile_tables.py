"""Create profile-service tables: profile_events (event store), outbox,
processed_inbound_events, profile_snapshot, profile_evolution,
profile_data_keys.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate.

Revision ID: 0001
Revises:
Create Date: 2026-08-24

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
        "profile_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_profile_events_aggregate_id", "profile_events", ["aggregate_id"])
    op.create_index(
        "ix_profile_events_aggregate_sequence", "profile_events", ["aggregate_id", "sequence"]
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
        "profile_snapshot",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("consent_granted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("weight_kg", sa.String(512), nullable=True),
        sa.Column("height_cm", sa.String(512), nullable=True),
        sa.Column("age", sa.String(512), nullable=True),
        sa.Column("sex", sa.String(512), nullable=True),
        sa.Column("activity_level", sa.String(512), nullable=True),
        sa.Column("goal_type", sa.String(16), nullable=True),
        sa.Column("goal_target_value", sa.String(512), nullable=True),
        sa.Column("goal_target_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "profile_evolution",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_index("ix_profile_evolution_user_id", "profile_evolution", ["user_id"])
    op.create_index("ix_profile_evolution_metric", "profile_evolution", ["metric"])
    op.create_index(
        "ix_profile_evolution_user_metric_recorded",
        "profile_evolution",
        ["user_id", "metric", "recorded_at"],
    )

    op.create_table(
        "profile_data_keys",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wrapped_data_key", sa.String(2048), nullable=False),
        sa.Column("kms_key_id", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("profile_data_keys")
    op.drop_index("ix_profile_evolution_user_metric_recorded", table_name="profile_evolution")
    op.drop_index("ix_profile_evolution_metric", table_name="profile_evolution")
    op.drop_index("ix_profile_evolution_user_id", table_name="profile_evolution")
    op.drop_table("profile_evolution")
    op.drop_table("profile_snapshot")
    op.drop_table("processed_inbound_events")
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_profile_events_aggregate_sequence", table_name="profile_events")
    op.drop_index("ix_profile_events_aggregate_id", table_name="profile_events")
    op.drop_table("profile_events")
