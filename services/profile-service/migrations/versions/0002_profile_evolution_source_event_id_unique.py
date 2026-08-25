"""Add a unique index on profile_evolution.source_event_id so that
replaying profile_events (RabbitMQ at-least-once redelivery, or a full
scripts/rebuild_read_models.py replay) is idempotent -- applying the same
event twice must not create a duplicate evolution row.

Additive only (CREATE UNIQUE INDEX) -- does not trigger the
destructive-change approval gate (database-migrations SKILL.md).

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-25

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_profile_evolution_source_event_id_unique",
        "profile_evolution",
        ["source_event_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_profile_evolution_source_event_id_unique", table_name="profile_evolution")
