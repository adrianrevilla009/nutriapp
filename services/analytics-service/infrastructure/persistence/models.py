"""SQLAlchemy 2.x async ORM models -- infrastructure layer only.

Mirrors migrations/versions/0001_create_analytics_tables.py. The domain
layer never imports this module (ADR-0001); mapping to/from domain
objects happens in the Postgres*Repository adapters.

`food_entry_contributions`/`water_intake_contributions` and
`micronutrient_current_targets` are additions beyond the persisted
implementation plan's section 3 table list, discovered necessary during
implementation -- see `domain/ports/daily_log_summary_repository_port.py`'s
and `domain/ports/micronutrient_window_repository_port.py`'s docstrings
for why.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Date,
    Float,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = {datetime: TIMESTAMP(timezone=True)}


class DailyLogSummaryModel(Base):
    __tablename__ = "daily_log_summary"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, primary_key=True)
    calories_kcal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    water_ml: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    entries_logged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("ix_daily_log_summary_user_date", "user_id", "on_date"),)


class FoodEntryContributionModel(Base):
    """Per-entry ledger enabling exact reversal of `FoodEntryCorrected`/
    `FoodEntryDeleted` (neither event carries the amount being reversed --
    see the port docstring)."""

    __tablename__ = "food_entry_contributions"

    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    calories_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)


class WaterIntakeContributionModel(Base):
    __tablename__ = "water_intake_contributions"

    intake_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_ml: Mapped[float] = mapped_column(Float, nullable=False)


class MicronutrientWindowModel(Base):
    __tablename__ = "micronutrient_window"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nutrient: Mapped[str] = mapped_column(String(64), primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    target_min: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_micronutrient_window_user_nutrient_date", "user_id", "nutrient", "on_date"),
    )


class MicronutrientCurrentTargetModel(Base):
    """The target-in-effect-now per user/nutrient, updated by
    `HandleNutritionTargetUpdatedHandler` -- deliberately separate from
    `micronutrient_window` (whose rows are immutable snapshots once
    written) so a later target change never rewrites history."""

    __tablename__ = "micronutrient_current_targets"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nutrient: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_min: Mapped[float | None] = mapped_column(Float, nullable=True)


class WeightTrendModel(Base):
    __tablename__ = "weight_trend"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, primary_key=True)
    weight_kg_ciphertext: Mapped[str] = mapped_column(String(512), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False)


class AnomalyAlertModel(Base):
    """Append-only log of detected/published `NutrientDeficiencyDetected`
    signals -- also the 14-day cooldown dedup guard (implementation plan
    section 9 addendum, resolution 2)."""

    __tablename__ = "anomaly_alerts"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    signal: Mapped[str] = mapped_column(String(64), nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_anomaly_alerts_user_signal_detected_at", "user_id", "signal", "detected_at"),
    )


class EntitlementCacheModel(Base):
    __tablename__ = "entitlement_cache"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    entitled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedDiaryEventModel(Base):
    __tablename__ = "processed_diary_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedProfileEventModel(Base):
    __tablename__ = "processed_profile_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedNutritionCalculationEventModel(Base):
    __tablename__ = "processed_nutrition_calculation_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedEntitlementEventModel(Base):
    __tablename__ = "processed_entitlement_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ExportAuditLogModel(Base):
    """Immutable, append-only -- CLAUDE.md section 2.8's mandatory
    data-export audit trail. Lives in the `analytics_audit` schema
    (separate from every operational projection table above), with
    `UPDATE`/`DELETE` revoked at the Postgres level from the connection
    the application actually writes through -- see
    migrations/versions/0002_export_audit_log_compliance.py and
    `infrastructure/composition_root.py`'s `AUDIT_WRITER_ROLE`/
    `Container.audit_engine` (same `SET ROLE`-per-connection mechanism as
    identity-service's/profile-service's own audit tables -- CLAUDE.md
    section 2.8, docs/observability-and-audit.md section 4.3).

    `export_id`/`requested_at` play the role of the standard
    `audit_id`/`occurred_at` fields from docs/observability-and-audit.md
    section 4.2; `outcome`/`actor_id`/`action`/`target_type`/`target_id`/
    `correlation_id` were added to close a schema-drift gap a security
    review found (the table previously had none of them). `user_id` is
    kept as-is for backward compatibility with the already-applied 0001
    migration and is always equal to `actor_id` for this service today
    (every export is self-service -- there is no on-behalf-of actor in
    NutriApp's single-tenant B2C model, ADR-0018); `actor_id` is the
    schema-mandated field name and the one new code should read.
    """

    __tablename__ = "export_audit_log"
    __table_args__ = (
        Index("ix_export_audit_log_user_id", "user_id"),
        Index("ix_export_audit_log_correlation_id", "correlation_id"),
        {"schema": "analytics_audit"},
    )

    export_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(nullable=False)
    export_format: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # -- fields added by migrations/versions/0002_export_audit_log_compliance.py --
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, server_default="success")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audit_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class OutboxModel(Base):
    __tablename__ = "outbox"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_outbox_unpublished", "published_at"),)
