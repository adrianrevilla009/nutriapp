"""SQLAlchemy 2.x async ORM models — infrastructure layer only.

Mirrors migrations/versions/0001_create_catalog_tables.py. The domain
layer never imports this module (ADR-0001); mapping to/from domain
objects happens in the Postgres*Repository adapters.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import TIMESTAMP, Computed, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = {datetime: TIMESTAMP(timezone=True)}


# Shared with migrations/versions/0001_create_catalog_tables.py's raw-SQL
# `ADD COLUMN ... GENERATED ALWAYS AS (...)` — kept identical in both
# places deliberately (the migration is authoritative for production
# schema history; declaring it here too via `Computed(persisted=True)`
# lets `Base.metadata.create_all` produce the same generated column for
# fast, migration-free integration tests, per testing-strategy SKILL.md).
_SEARCH_VECTOR_EXPRESSION = (
    "setweight(to_tsvector('simple', coalesce(name, '')), 'A') || "
    "setweight(to_tsvector('simple', coalesce(brand, '')), 'B') || "
    "setweight(to_tsvector('simple', coalesce(category, '')), 'C')"
)


class ProductModel(Base):
    __tablename__ = "products"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    barcode: Mapped[str | None] = mapped_column(String(14), unique=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nutrient_panel: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    dietary_tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, default=list)
    allergen_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list
    )
    package_size: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    price: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sources: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, default=list)
    catalogued_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
    # Generated column, GIN-indexed for full-text search (ADR-0012).
    # `Computed(persisted=True)` tells SQLAlchemy this is server-computed
    # (`GENERATED ALWAYS AS ... STORED`) and to exclude it from every
    # INSERT/UPDATE statement it emits — never writable through the ORM.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_SEARCH_VECTOR_EXPRESSION, persisted=True), nullable=True
    )


class ProductSourceModel(Base):
    """One row per source-per-product — that source's raw last-seen
    values (implementation plan section 7): needed for the conflict-
    resolution rule and for re-deriving `ProductUpdated.changed_fields`.
    No raw source data is ever silently discarded on conflict."""

    __tablename__ = "product_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index(
            "ix_product_sources_source_product",
            "source",
            "source_product_id",
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


class IngestionRunModel(Base):
    """Audit trail for each ingestion run (implementation plan section 3):
    source, started_at, finished_at, items_seen/added/updated/skipped,
    status."""

    __tablename__ = "ingestion_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    items_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
