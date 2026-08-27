"""SQLAlchemy 2.x async ORM models -- infrastructure layer only.

Mirrors migrations/versions/0001_create_food_recognition_tables.py. The
domain layer never imports this module (ADR-0001); mapping to/from domain
objects happens in the Postgres*Repository adapters.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import TIMESTAMP, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = {datetime: TIMESTAMP(timezone=True)}


class PhotoAnalysisModel(Base):
    """Append-only audit record -- one row per photo-analysis request,
    success or failure alike (implementation plan section 2)."""

    __tablename__ = "photo_analyses"

    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")


class BarcodeLookupModel(Base):
    """Append-only audit record -- one row per barcode decode-and-lookup
    request (implementation plan section 2). No domain event is published
    for these (section 1, acceptance criterion 4)."""

    __tablename__ = "barcode_lookups"

    lookup_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False)
    decoded_barcode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    matched_product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


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
