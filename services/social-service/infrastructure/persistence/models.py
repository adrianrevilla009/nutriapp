"""SQLAlchemy 2.x async ORM models -- infrastructure layer only.

Mirrors migrations/versions/0001_create_social_tables.py. The domain
layer never imports this module (ADR-0001); mapping to/from domain
objects happens in the Postgres*Repository adapters.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import TIMESTAMP, Boolean, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[type, TIMESTAMP]] = {datetime: TIMESTAMP(timezone=True)}


class FollowModel(Base):
    __tablename__ = "follows"

    follow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    follower_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    followee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    followed_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_follows_follower_followee"),
        Index("ix_follows_follower_id", "follower_id"),
        Index("ix_follows_followee_id", "followee_id"),
    )


class FeedEntryModel(Base):
    __tablename__ = "feed_entries"

    recipe_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_feed_entries_author_id", "author_id"),)


class EntitlementCacheModel(Base):
    __tablename__ = "entitlement_cache"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    entitled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedEntitlementEventModel(Base):
    """Idempotency ledger for `BillingEventsConsumer` -- see that
    consumer's own docstring for why it's keyed by `event_id` alone."""

    __tablename__ = "processed_entitlement_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class ProcessedRecipeEventModel(Base):
    """Idempotency ledger for `RecipeEventsConsumer` -- a separate table
    from `processed_entitlement_events` by design (two independent
    consumers, two independent ledgers, implementation plan section 3)."""

    __tablename__ = "processed_recipe_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(nullable=False)


class OutboxModel(Base):
    """Backs `PostgresOutboxRepository` -- one row per `UserFollowed`/
    `UserUnfollowed` waiting for (or already relayed by)
    `OutboxRelayWorker`. `published_at IS NULL` is exactly the
    "still pending relay" predicate the worker polls on."""

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
