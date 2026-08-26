"""SQLAlchemy 2.x async ORM models -- infrastructure layer only.

Mirrors migrations/versions/0001_create_diary_tables.py. The domain layer
never imports this module (ADR-0001).

Single `diary_events` table, discriminated by `aggregate_type`
(food_entry | water_intake_entry | fasting_window | meal_plan_entry),
shared by one PostgresEventStore adapter across all 4 aggregate types
(implementation plan section 3/9.5) -- a pragmatic intra-service
normalization call, not a violation of CLAUDE.md section 2.5's "no shared
schemas across service boundaries."
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, Identity, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    # Every datetime in this service is timezone-aware (UTC) at the domain
    # layer -- map every `datetime` column to TIMESTAMP WITH TIME ZONE so
    # asyncpg never has to compare a naive and an aware datetime.
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = dict.fromkeys(
        [datetime], TIMESTAMP(timezone=True)
    )


class DiaryEventModel(Base):
    """Event store -- append-only, source of truth (ADR-0002).

    `aggregate_sequence` is the position of this event WITHIN its own
    (aggregate_type, aggregate_id) stream, assigned by the application
    layer (len(loaded_stream)) and enforced unique per
    (aggregate_type, aggregate_id) by the composite unique index below --
    this is the optimistic-concurrency guard (test-plan section 2's
    concurrent-append case): two writers racing to append the same
    position for the same aggregate cannot both succeed.
    """

    __tablename__ = "diary_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index(
            "ix_diary_events_aggregate_sequence",
            "aggregate_type",
            "aggregate_id",
            "sequence",
        ),
        Index(
            "ux_diary_events_aggregate_position",
            "aggregate_type",
            "aggregate_id",
            "aggregate_sequence",
            unique=True,
        ),
    )


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
    """Idempotency dedup for consumed events (messaging-conventions
    SKILL.md) -- diary_event_projector_consumer's own dedup, since it
    consumes diary-service's own published events (implementation plan
    section 9.4/test-plan section 5)."""

    __tablename__ = "processed_inbound_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class FoodEntryViewModel(Base):
    """food_entries_view -- disposable, rebuildable by replaying
    diary_events (cqrs-event-sourcing SKILL.md)."""

    __tablename__ = "food_entries_view"

    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    meal_slot: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    calories_kcal: Mapped[float] = mapped_column(nullable=False, default=0.0)
    protein_g: Mapped[float] = mapped_column(nullable=False, default=0.0)
    carbs_g: Mapped[float] = mapped_column(nullable=False, default=0.0)
    fat_g: Mapped[float] = mapped_column(nullable=False, default=0.0)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_food_entries_view_user_occurred", "user_id", "occurred_at"),)


class WaterIntakeViewModel(Base):
    """water_intake_view -- disposable, rebuildable by replaying diary_events."""

    __tablename__ = "water_intake_view"

    intake_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    amount_ml: Mapped[float] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    removed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_water_intake_view_user_occurred", "user_id", "occurred_at"),)


class FastingWindowViewModel(Base):
    """fasting_windows_view -- disposable, rebuildable by replaying diary_events."""

    __tablename__ = "fasting_windows_view"

    window_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_fasting_windows_view_user_started", "user_id", "started_at"),)


class MealPlanViewModel(Base):
    """meal_plan_view -- disposable, rebuildable by replaying diary_events."""

    __tablename__ = "meal_plan_view"

    plan_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    meal_slot: Mapped[str] = mapped_column(String(16), nullable=False)
    planned_for: Mapped[datetime] = mapped_column(nullable=False, index=True)
    removed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_meal_plan_view_user_planned", "user_id", "planned_for"),)


class DailySummaryViewModel(Base):
    """daily_summary_view -- the "hot aggregate" cached in Redis
    (implementation plan section 7). Disposable, rebuildable by
    recomputing from food_entries_view/water_intake_view/
    fasting_windows_view (themselves rebuildable by replaying
    diary_events) -- see
    infrastructure/persistence/projectors/daily_summary_projector.py.
    """

    __tablename__ = "daily_summary_view"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    summary_date: Mapped[str] = mapped_column(String(10), primary_key=True)  # ISO date
    total_calories_kcal: Mapped[float] = mapped_column(nullable=False, default=0.0)
    total_protein_g: Mapped[float] = mapped_column(nullable=False, default=0.0)
    total_carbs_g: Mapped[float] = mapped_column(nullable=False, default=0.0)
    total_fat_g: Mapped[float] = mapped_column(nullable=False, default=0.0)
    total_water_ml: Mapped[float] = mapped_column(nullable=False, default=0.0)
    fasting_windows_ended: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
