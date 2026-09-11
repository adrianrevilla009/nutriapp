"""create processed_entitlement_events table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-11

Additive-only (database-migrations SKILL.md's expand/contract pattern) --
new idempotency ledger table for billing_events_consumer.py
(implementation plan addendum, 2026-09-08: `entitlement_cache` live
writer approved). Does not touch any existing table -- `entitlement_cache`
itself keeps the exact columns migration 0001 created; only the
application-layer meaning of how its `updated_at` value is populated
changes (now the event's own `granted_at`/`revoked_at`, previously
wall-clock time), which requires no schema change."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_entitlement_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processed_entitlement_events")
