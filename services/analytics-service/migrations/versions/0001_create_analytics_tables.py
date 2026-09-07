"""Create analytics-service tables: daily_log_summary,
food_entry_contributions, water_intake_contributions, micronutrient_window,
micronutrient_current_targets, weight_trend, anomaly_alerts,
entitlement_cache, four processed_*_events ledgers, export_audit_log,
outbox.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate. New
service, no existing schema to preserve compatibility with.

`food_entry_contributions`/`water_intake_contributions`/
`micronutrient_current_targets` are additions beyond the persisted
implementation plan's section 3 table list -- see
`domain/ports/daily_log_summary_repository_port.py`'s and
`domain/ports/micronutrient_window_repository_port.py`'s docstrings for
why they're necessary.

Revision ID: 0001
Revises:
Create Date: 2026-09-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_event_ledger_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "daily_log_summary",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("on_date", sa.Date(), primary_key=True),
        sa.Column("calories_kcal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("protein_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carbs_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fat_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("water_ml", sa.Float(), nullable=False, server_default="0"),
        sa.Column("entries_logged_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_daily_log_summary_user_date", "daily_log_summary", ["user_id", "on_date"])

    op.create_table(
        "food_entry_contributions",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("calories_kcal", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
    )

    op.create_table(
        "water_intake_contributions",
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("amount_ml", sa.Float(), nullable=False),
    )

    op.create_table(
        "micronutrient_window",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nutrient", sa.String(64), primary_key=True),
        sa.Column("on_date", sa.Date(), primary_key=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("target_min", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_micronutrient_window_user_nutrient_date",
        "micronutrient_window",
        ["user_id", "nutrient", "on_date"],
    )

    op.create_table(
        "micronutrient_current_targets",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nutrient", sa.String(64), primary_key=True),
        sa.Column("target_min", sa.Float(), nullable=True),
    )

    op.create_table(
        "weight_trend",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("on_date", sa.Date(), primary_key=True),
        sa.Column("weight_kg_ciphertext", sa.String(512), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "anomaly_alerts",
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal", sa.String(64), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_anomaly_alerts_user_signal_detected_at",
        "anomaly_alerts",
        ["user_id", "signal", "detected_at"],
    )

    op.create_table(
        "entitlement_cache",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entitled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    _create_event_ledger_table("processed_diary_events")
    _create_event_ledger_table("processed_profile_events")
    _create_event_ledger_table("processed_nutrition_calculation_events")
    _create_event_ledger_table("processed_entitlement_events")

    op.create_table(
        "export_audit_log",
        sa.Column("export_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", sa.String(64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("export_format", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_export_audit_log_user_id", "export_audit_log", ["user_id"])

    op.create_table(
        "outbox",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unpublished", "outbox", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_export_audit_log_user_id", table_name="export_audit_log")
    op.drop_table("export_audit_log")
    op.drop_table("processed_entitlement_events")
    op.drop_table("processed_nutrition_calculation_events")
    op.drop_table("processed_profile_events")
    op.drop_table("processed_diary_events")
    op.drop_table("entitlement_cache")
    op.drop_index("ix_anomaly_alerts_user_signal_detected_at", table_name="anomaly_alerts")
    op.drop_table("anomaly_alerts")
    op.drop_table("weight_trend")
    op.drop_table("micronutrient_current_targets")
    op.drop_index("ix_micronutrient_window_user_nutrient_date", table_name="micronutrient_window")
    op.drop_table("micronutrient_window")
    op.drop_table("water_intake_contributions")
    op.drop_table("food_entry_contributions")
    op.drop_index("ix_daily_log_summary_user_date", table_name="daily_log_summary")
    op.drop_table("daily_log_summary")
