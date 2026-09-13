"""add health_adjacent_flagged to chat_audit_log

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12

Additive-only (database-migrations SKILL.md's expand/contract pattern) --
adds a single nullable-free boolean column (with a server default so the
migration is backward-compatible for any row written before this
release) to the existing chat_audit_log table. Implements the security-
review operational mitigation approved in the implementation plan's
2026-09-12 addendum: log flagged-vs-unflagged health-adjacent-looking
queries for future manual drift review of health_topic_classifier's
precision/recall. Does not touch any other table or any existing column
on chat_audit_log."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_audit_log",
        sa.Column(
            "health_adjacent_flagged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_audit_log", "health_adjacent_flagged")
