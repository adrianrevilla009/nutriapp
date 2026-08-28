"""SQLAlchemy 2.x async ORM models -- infrastructure layer only.

Mirrors migrations/versions/0001_create_notification_tables.py. The
domain layer never imports this module (ADR-0001); mapping to/from domain
objects happens in the Postgres*Repository adapters. CQRS, read side only
(implementation plan section 2) -- these are conventional, mutable
operational/read-model tables, never an event-sourced write aggregate.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import ClassVar

from sqlalchemy import TIMESTAMP, Boolean, Index, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = {datetime: TIMESTAMP(timezone=True)}


class ReminderScheduleModel(Base):
    __tablename__ = "reminder_schedule"

    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    source_aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    due_at: Mapped[datetime] = mapped_column(nullable=False)
    relevance_expires_at: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    next_eligible_check_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source_aggregate_id", "category", name="uq_reminder_schedule_source_category"
        ),
        Index("ix_reminder_schedule_status_due_at", "status", "due_at"),
    )


class ProcessedNotificationModel(Base):
    __tablename__ = "processed_notifications"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class DeliveryLogModel(Base):
    __tablename__ = "delivery_log"

    delivery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    template_name: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class SuppressionListModel(Base):
    __tablename__ = "suppression_list"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), primary_key=True)
    address_or_device: Mapped[str] = mapped_column(String(320), primary_key=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    suppressed_at: Mapped[datetime] = mapped_column(nullable=False)


class NotificationPreferenceModel(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quiet_hours_start: Mapped[time] = mapped_column(Time, nullable=False)
    quiet_hours_end: Mapped[time] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
