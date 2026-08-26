"""Create audit_records: profile-service's first audit-trail capability
(implementation plan Addendum 2, requirement 6). Every call to
`POST /internal/v1/profile/{user_id}/reveal-metrics`, success or failure,
writes exactly one row here.

CREATE TABLE-only -- additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate.

Also grants INSERT-only privileges on audit_records to a dedicated
`profile_service_audit_writer` role (created out-of-band by
infra/k8s/charts/_lib/templates/_db-provision-job.tpl, which runs with
sufficient privilege to CREATE ROLE -- this migration runs as this
service's own DB_ROLE, which does not) -- see
infrastructure/composition_root.py's `AUDIT_WRITER_ROLE` and
observability-audit SKILL.md. Mirrors identity-service's
`identity_service_audit_writer` grant in
migrations/versions/0001_create_identity_tables.py exactly, scoped to
this service's own table/role name.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_WRITER_ROLE = "profile_service_audit_writer"


def upgrade() -> None:
    op.create_table(
        "audit_records",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_records_target", "audit_records", ["target_type", "target_id"])

    # Append-only audit trail: dedicated role can INSERT but never
    # UPDATE/DELETE audit_records (observability-audit SKILL.md). If this
    # GRANT fails with "role does not exist", the _db-provision-job's
    # role-creation step did not run first -- that ordering is mandatory,
    # not optional (see identity-service's identical precedent).
    op.execute(f'GRANT INSERT ON audit_records TO "{AUDIT_WRITER_ROLE}";')
    op.execute(f'REVOKE UPDATE, DELETE ON audit_records FROM "{AUDIT_WRITER_ROLE}";')


def downgrade() -> None:
    op.execute(f'REVOKE INSERT ON audit_records FROM "{AUDIT_WRITER_ROLE}";')
    op.drop_index("ix_audit_records_target", table_name="audit_records")
    op.drop_table("audit_records")
