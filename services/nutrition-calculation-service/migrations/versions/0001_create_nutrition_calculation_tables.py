"""Create nutrition-calculation-service tables: nutrition_targets,
nutrition_target_history, daily_nutrition_totals, nutrient_panel_mirror,
user_metrics_snapshot, outbox, processed_events.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate.

SECURITY-CRITICAL (implementation plan Addendum 1, security sub-addendum
requirement 8): `user_metrics_snapshot` intentionally has NO `weight_kg`/
`height_cm`/`age`/`sex` columns -- metadata only. Do not add them in a
future migration without a new, explicit human-approved decision -- doing
so would create a second, unencrypted, non-crypto-shreddable copy of GDPR
Article 9 special-category data outside profile-service's erasure design
(ADR-0023).

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


def _target_columns() -> list[sa.Column]:
    return [
        sa.Column("bmr_kcal", sa.Float(), nullable=False),
        sa.Column("tdee_kcal", sa.Float(), nullable=False),
        sa.Column("calorie_target_kcal", sa.Float(), nullable=False),
        sa.Column("protein_g_min", sa.Float(), nullable=False),
        sa.Column("protein_g_max", sa.Float(), nullable=False),
        sa.Column("fat_g_min", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("carbs_floored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("goal_type", sa.String(16), nullable=False),
        sa.Column("activity_level", sa.String(16), nullable=False),
        sa.Column("sex_constant_used", sa.String(8), nullable=False),
        sa.Column("clamped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("clamp_reason", sa.String(255), nullable=True),
        sa.Column("formula_version", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "nutrition_targets",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_target_columns(),
    )

    op.create_table(
        "nutrition_target_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        *_target_columns(),
    )
    op.create_index("ix_nutrition_target_history_user_id", "nutrition_target_history", ["user_id"])

    op.create_table(
        "daily_nutrition_totals",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("total_date", sa.Date(), primary_key=True),
        sa.Column("calories_kcal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("protein_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carbs_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fat_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("micronutrients", postgresql.JSONB(), nullable=True),
        sa.Column(
            "micronutrients_status", sa.String(16), nullable=False, server_default="unavailable"
        ),
        sa.Column("is_estimated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("entries", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "nutrient_panel_mirror",
        sa.Column("source_reference_id", sa.String(64), primary_key=True),
        sa.Column("panel", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # SECURITY-CRITICAL: metadata only, see module docstring.
    op.create_table(
        "user_metrics_snapshot",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("formula_version", sa.String(32), nullable=False),
        sa.Column("sex_constant_used", sa.String(8), nullable=True),
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
        "processed_events",
        sa.Column("consumer_name", sa.String(128), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("user_metrics_snapshot")
    op.drop_table("nutrient_panel_mirror")
    op.drop_table("daily_nutrition_totals")
    op.drop_index("ix_nutrition_target_history_user_id", table_name="nutrition_target_history")
    op.drop_table("nutrition_target_history")
    op.drop_table("nutrition_targets")
