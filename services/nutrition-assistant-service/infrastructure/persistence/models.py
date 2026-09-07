"""SQLAlchemy 2.x async ORM models -- infrastructure layer only.

Mirrors migrations/versions/0001_create_nutrition_assistant_tables.py. The
domain layer never imports this module (ADR-0001); mapping to/from domain
objects happens in the Postgres*Repository adapters.

Conventional persistence / event-driven CRUD (ADR-0002 addendum) -- no
event-sourced write aggregate. `diary_history`/`nutrition_history`/
`analytics_signals` are structured CQRS-style read projections, fed
incrementally by this service's three message consumers (never a
full-history rewrite per event, per
.claude/agents/nutrition-assistant-agent.md)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, ClassVar

from sqlalchemy import TIMESTAMP, Boolean, Date, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = {datetime: TIMESTAMP(timezone=True)}


class FoodEntryHistoryModel(Base):
    """One row per diary-service FoodEntryLogged/Corrected entry, keyed by
    entry_id (upserted, never accumulated) -- diary_history's food-entry
    half."""

    __tablename__ = "food_entry_history"

    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_food_entry_history_user_id", "user_id"),)


class WaterIntakeHistoryModel(Base):
    __tablename__ = "water_intake_history"

    intake_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_water_intake_history_user_id", "user_id"),)


class NutritionValueHistoryModel(Base):
    """One row per (user_id, scope, reference_id) -- upserted on every
    NutritionValueRecomputed for that scope, never accumulated."""

    __tablename__ = "nutrition_value_history"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), primary_key=True)
    reference_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    on_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)

    __table_args__ = (Index("ix_nutrition_value_history_user_id", "user_id"),)


class NutritionTargetHistoryModel(Base):
    """The current target summary per user -- upserted on every
    NutritionTargetUpdated, one row per user (never accumulated)."""

    __tablename__ = "nutrition_target_history"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)


class AnalyticsSignalModel(Base):
    """One row per (user_id, signal) -- upserted on every
    NutrientDeficiencyDetected for that signal. `disclaimer` is stored and
    surfaced verbatim, never re-worded (implementation plan section 5)."""

    __tablename__ = "analytics_signal_history"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    signal: Mapped[str] = mapped_column(String(64), primary_key=True)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    disclaimer: Mapped[str] = mapped_column(String(2000), nullable=False)

    __table_args__ = (Index("ix_analytics_signal_history_user_id", "user_id"),)


class EntitlementCacheModel(Base):
    __tablename__ = "entitlement_cache"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    entitled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedDiaryEventModel(Base):
    __tablename__ = "processed_diary_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedNutritionCalculationEventModel(Base):
    __tablename__ = "processed_nutrition_calculation_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedAnalyticsEventModel(Base):
    __tablename__ = "processed_analytics_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ChatAuditLogModel(Base):
    """Write-only traceability log -- NOT a queryable conversation-resume
    feature (implementation plan section 9 resolution 6). No read/list
    method exists on ChatAuditRepositoryPort at all."""

    __tablename__ = "chat_audit_log"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    query: Mapped[str] = mapped_column(String(4000), nullable=False)
    retrieved_record_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(16), nullable=False)
    had_sufficient_context: Mapped[bool] = mapped_column(Boolean, nullable=False)
    disclaimer_included: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_chat_audit_log_user_id", "user_id"),)


class OutboxModel(Base):
    """Scaffolded for architectural symmetry -- unused this pass, no live
    publisher wired to it (implementation plan section 5)."""

    __tablename__ = "outbox"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_outbox_unpublished", "published_at"),)
