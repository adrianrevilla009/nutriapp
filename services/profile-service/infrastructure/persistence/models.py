"""SQLAlchemy 2.x async ORM models -- infrastructure layer only.

Mirrors migrations/versions/0001_create_profile_tables.py. The domain
layer never imports this module (ADR-0001).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, ClassVar

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, Date, Identity, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    # Every datetime in this service is timezone-aware (UTC) at the domain
    # layer -- map every `datetime` column to TIMESTAMP WITH TIME ZONE so
    # asyncpg never has to compare a naive and an aware datetime.
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = dict.fromkeys(
        [datetime], TIMESTAMP(timezone=True)
    )


class ProfileEventModel(Base):
    """Event store -- append-only, source of truth (ADR-0002). Payload
    values that are Article 9 special-category biometric/health data are
    ALWAYS stored encrypted (per-user envelope encryption) -- see
    infrastructure/security/kms_envelope_data_encryption.py and
    application/dto/event_crypto.py, which decides which fields."""

    __tablename__ = "profile_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_profile_events_aggregate_sequence", "aggregate_id", "sequence"),)


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
    SKILL.md) -- currently only UserRegistered."""

    __tablename__ = "processed_inbound_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ProfileSnapshotModel(Base):
    """Current-snapshot read model -- disposable, rebuildable by replaying
    profile_events (cqrs-event-sourcing SKILL.md). Encrypted-field columns
    hold the same ciphertext as the corresponding event payload field --
    decrypted only at query time (application/queries/get_profile_snapshot.py)."""

    __tablename__ = "profile_snapshot"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    consent_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weight_kg: Mapped[str | None] = mapped_column(String(512), nullable=True)
    height_cm: Mapped[str | None] = mapped_column(String(512), nullable=True)
    age: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(512), nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(512), nullable=True)
    goal_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    goal_target_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    goal_target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class ProfileEvolutionModel(Base):
    """Evolution-timeline read model -- one row per metric-recording
    event; corrections are appended as new rows, never overwritten
    (cqrs-event-sourcing SKILL.md)."""

    __tablename__ = "profile_evolution"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    # Unique so that replaying profile_events (whether via at-least-once
    # RabbitMQ redelivery driving a synchronous apply() twice, or the
    # scripts/rebuild_read_models.py full-replay path) is idempotent --
    # PostgresEvolutionProjector.apply() upserts ON CONFLICT DO NOTHING
    # against this constraint, so a rebuild is genuinely safe to run
    # without truncating first (though the rebuild script truncates first
    # anyway, as the documented/expected path).
    source_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        Index("ix_profile_evolution_user_metric_recorded", "user_id", "metric", "recorded_at"),
        Index("ix_profile_evolution_source_event_id_unique", "source_event_id", unique=True),
    )


class ProfileDataKeyModel(Base):
    """Per-user envelope-encryption key material (implementation plan
    Addendum 1: profile-service owns its own key store, KMS-wrapped).
    `wrapped_data_key` is the KMS-encrypted (ciphertext) data-encryption
    key -- this table never stores a plaintext key. Deleting a user's row
    here (a future, out-of-scope erasure flow, plan section 9.2) makes
    every historical encrypted event payload for that user permanently
    unreadable -- crypto-shredding."""

    __tablename__ = "profile_data_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    wrapped_data_key: Mapped[str] = mapped_column(String(2048), nullable=False)
    kms_key_id: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
