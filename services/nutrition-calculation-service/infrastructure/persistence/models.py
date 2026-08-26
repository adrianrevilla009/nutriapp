"""SQLAlchemy 2.x async ORM models -- infrastructure layer only.

Mirrors migrations/versions/0001_create_nutrition_calculation_tables.py.
The domain layer never imports this module (ADR-0001); mapping to/from
domain objects happens in the Postgres*Repository adapters.

**Security-critical (implementation plan Addendum 1, security sub-addendum
requirement 8):** `UserMetricsSnapshotModel` has NO `weight_kg`/`height_cm`/
`age`/`sex` columns -- metadata only. See
tests/integration/infrastructure/test_postgres_user_metrics_snapshot_repository.py's
schema-level negative test.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import TIMESTAMP, Boolean, Date, Float, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = {datetime: TIMESTAMP(timezone=True)}


class NutritionTargetModel(Base):
    __tablename__ = "nutrition_targets"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    bmr_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    tdee_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    calorie_target_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g_min: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g_max: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g_min: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_floored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    goal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    activity_level: Mapped[str] = mapped_column(String(16), nullable=False)
    sex_constant_used: Mapped[str] = mapped_column(String(8), nullable=False)
    clamped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clamp_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(nullable=False)


class NutritionTargetHistoryModel(Base):
    """Append-only timeline -- never updated or deleted in place (CQRS-lite
    read model for the history query, implementation plan section 2)."""

    __tablename__ = "nutrition_target_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    bmr_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    tdee_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    calorie_target_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g_min: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g_max: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g_min: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_floored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    goal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    activity_level: Mapped[str] = mapped_column(String(16), nullable=False)
    sex_constant_used: Mapped[str] = mapped_column(String(8), nullable=False)
    clamped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clamp_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(nullable=False)


class DailyNutritionTotalModel(Base):
    """One row per `(user_id, date)`, upsert (implementation plan section
    2). `entries` retains each contributing entry's own line (keyed by
    `entry_id`, JSONB) so a later `FoodEntryCorrected`/`FoodEntryDeleted`
    can upsert/remove a single contribution without needing to replay the
    whole day's history."""

    __tablename__ = "daily_nutrition_totals"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    total_date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    calories_kcal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    micronutrients: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    micronutrients_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unavailable"
    )
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entries: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class NutrientPanelMirrorModel(Base):
    """Local, read-only, denormalized mirror of catalog-service's nutrient
    panel (implementation plan section 6(c)), keyed by
    `source_reference_id` (catalog-service's `product_id`)."""

    __tablename__ = "nutrient_panel_mirror"

    source_reference_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    panel: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class UserMetricsSnapshotModel(Base):
    """Metadata-only record of the last successful ProfileRevealPort fetch
    (implementation plan Addendum 1, security sub-addendum requirement 8).

    SECURITY-CRITICAL: this table must NEVER gain a `weight_kg`/`height_cm`/
    `age`/`sex` column -- see the module docstring and the schema-level
    negative test guarding this."""

    __tablename__ = "user_metrics_snapshot"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    last_fetched_at: Mapped[datetime] = mapped_column(nullable=False)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    sex_constant_used: Mapped[str | None] = mapped_column(String(8), nullable=True)


class OutboxModel(Base):
    __tablename__ = "outbox"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_outbox_unpublished", "published_at"),)


class ProcessedInboundEventModel(Base):
    """Idempotency dedup shared across all 3 inbound consumers, keyed by
    `(consumer_name, event_id)` (implementation plan section 3)."""

    __tablename__ = "processed_events"

    consumer_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)
