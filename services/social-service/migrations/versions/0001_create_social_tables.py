"""Create social-service tables: follows, feed_entries, entitlement_cache,
processed_entitlement_events, processed_recipe_events, outbox.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate. New
service, no existing schema to preserve compatibility with (implementation
plan section 7).

Revision ID: 0001
Revises:
Create Date: 2026-08-31

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
    """Shape shared by both idempotency ledgers below -- a bare
    `event_id` primary key plus `processed_at`, no foreign key, since each
    consumer's idempotency contract keys purely off the inbound
    `event_id`."""
    op.create_table(
        table_name,
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "follows",
        sa.Column("follow_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("followee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("followed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_follows_follower_followee"),
    )
    op.create_index("ix_follows_follower_id", "follows", ["follower_id"])
    op.create_index("ix_follows_followee_id", "follows", ["followee_id"])

    op.create_table(
        "feed_entries",
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feed_entries_author_id", "feed_entries", ["author_id"])

    op.create_table(
        "entitlement_cache",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entitled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    _create_event_ledger_table("processed_entitlement_events")
    _create_event_ledger_table("processed_recipe_events")

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
    op.drop_table("processed_recipe_events")
    op.drop_table("processed_entitlement_events")
    op.drop_table("entitlement_cache")
    op.drop_index("ix_feed_entries_author_id", table_name="feed_entries")
    op.drop_table("feed_entries")
    op.drop_index("ix_follows_followee_id", table_name="follows")
    op.drop_index("ix_follows_follower_id", table_name="follows")
    op.drop_table("follows")
