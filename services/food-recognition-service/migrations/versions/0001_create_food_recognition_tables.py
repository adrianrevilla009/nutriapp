"""Create food-recognition-service tables: photo_analyses,
barcode_lookups, outbox.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate.

Both `photo_analyses` and `barcode_lookups` are append-only audit records
(implementation plan section 2) -- one row per analysis/lookup request,
success or failure alike. No uploaded image bytes are ever stored here or
anywhere else (implementation plan section 1, acceptance criterion 6).

Revision ID: 0001
Revises:
Create Date: 2026-08-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photo_analyses",
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candidates", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False, server_default=""),
    )
    op.create_index("ix_photo_analyses_user_id", "photo_analyses", ["user_id"])

    op.create_table(
        "barcode_lookups",
        sa.Column("lookup_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decoded_barcode", sa.String(32), nullable=True),
        sa.Column("matched_product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_barcode_lookups_user_id", "barcode_lookups", ["user_id"])

    op.create_table(
        "outbox",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unpublished", "outbox", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_barcode_lookups_user_id", table_name="barcode_lookups")
    op.drop_table("barcode_lookups")
    op.drop_index("ix_photo_analyses_user_id", table_name="photo_analyses")
    op.drop_table("photo_analyses")
