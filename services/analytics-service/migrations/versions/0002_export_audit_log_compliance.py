"""Export-audit-trail compliance fix: move `export_audit_log` into its own
`analytics_audit` schema and add the audit-record fields
docs/observability-and-audit.md section 4.2 mandates
(`outcome`/`actor_id`/`action`/`target_type`/`target_id`/`correlation_id`),
plus grant append-only (INSERT/SELECT-only) privileges on the moved table
to a dedicated `analytics_service_audit_writer` role -- closing three
concrete gaps a security review found in the already-shipped export audit
trail (schema drift from the mandated shape, no DB-level append-only
enforcement, and -- fixed separately in
application/queries/get_report.py -- rejected export attempts never being
audited at all).

Additive by construction (database-migrations SKILL.md): no `DROP TABLE`,
no `DROP COLUMN`, no narrowing type change. `export_audit_log` is MOVED
(via `ALTER TABLE ... SET SCHEMA`, which preserves the table and all of
its existing rows -- there are none in any deployed environment yet, but
this is not a row-losing operation regardless), not dropped and
recreated. The new columns are added nullable (`outcome` gets a
`server_default` of `'success'`, since every row written before this
migration was, by construction, a successful export under the pre-fix
code path; the rest have no safe default and are left NULL for any
pre-existing row) -- a later "contract" migration could enforce NOT NULL
on `actor_id`/`action`/`target_type`/`target_id`/`correlation_id` once
100% of rows post-date this fix, per the expand/contract pattern
(.claude/skills/database-migrations/SKILL.md); not done here since
enforcing that today would require a data backfill this migration cannot
safely perform for historical rows that never captured this data.

Grants INSERT/SELECT-only privileges on `analytics_audit.export_audit_log`
to `analytics_service_audit_writer` (mirrors identity-service's
`identity_service_audit_writer` grant in
migrations/versions/0001_create_identity_tables.py and profile-service's
`profile_service_audit_writer` grant in
migrations/versions/0003_create_audit_records_table.py exactly, scoped to
this service's own table/role name). The role itself is created out of
band by infra/k8s/charts/_lib/templates/_db-provision-job.tpl, which runs
as the RDS master user (CREATEROLE) BEFORE this migration ever runs --
this migration runs as this service's own DB_ROLE (`analytics_service`),
which does not have CREATEROLE, but which the provisioning script already
granted membership in `analytics_service_audit_writer` to (see that
template's own header comment) -- table ownership plus that membership is
sufficient to GRANT/REVOKE privileges on the table to that
already-existing role without CREATEROLE. If this GRANT fails with "role
does not exist", the provisioning Job did not run first -- that ordering
is mandatory, not optional.

Per .claude/skills/database-migrations/SKILL.md: "Any migration affecting
the audit trail schema" requires explicit human confirmation before
execution against a real environment -- this migration is written and
tested (against an ephemeral testcontainers Postgres) but is NOT applied
to any real database by this change; that remains a separate, explicitly
approved deploy step.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SCHEMA = "analytics_audit"
AUDIT_WRITER_ROLE = "analytics_service_audit_writer"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {AUDIT_SCHEMA};")

    # Move the table (preserves all existing rows/indexes/constraints) into
    # the dedicated audit schema -- docs/observability-and-audit.md section
    # 4.3: "audit records are stored ... in a separate schema from
    # operational data".
    op.execute(f"ALTER TABLE export_audit_log SET SCHEMA {AUDIT_SCHEMA};")

    op.add_column(
        "export_audit_log",
        sa.Column("outcome", sa.String(16), nullable=False, server_default="success"),
        schema=AUDIT_SCHEMA,
    )
    op.add_column(
        "export_audit_log",
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=AUDIT_SCHEMA,
    )
    op.add_column(
        "export_audit_log",
        sa.Column("action", sa.String(64), nullable=True),
        schema=AUDIT_SCHEMA,
    )
    op.add_column(
        "export_audit_log",
        sa.Column("target_type", sa.String(64), nullable=True),
        schema=AUDIT_SCHEMA,
    )
    op.add_column(
        "export_audit_log",
        sa.Column("target_id", sa.String(128), nullable=True),
        schema=AUDIT_SCHEMA,
    )
    op.add_column(
        "export_audit_log",
        sa.Column("correlation_id", sa.String(64), nullable=True),
        schema=AUDIT_SCHEMA,
    )
    op.add_column(
        "export_audit_log",
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        schema=AUDIT_SCHEMA,
    )

    op.create_index(
        "ix_export_audit_log_correlation_id",
        "export_audit_log",
        ["correlation_id"],
        schema=AUDIT_SCHEMA,
    )

    # Append-only enforcement, genuinely at the Postgres level (not just
    # application-layer discipline): the writer role can INSERT/SELECT,
    # never UPDATE/DELETE.
    op.execute(f'GRANT USAGE ON SCHEMA {AUDIT_SCHEMA} TO "{AUDIT_WRITER_ROLE}";')
    op.execute(f'GRANT SELECT, INSERT ON {AUDIT_SCHEMA}.export_audit_log TO "{AUDIT_WRITER_ROLE}";')
    op.execute(
        f'REVOKE UPDATE, DELETE ON {AUDIT_SCHEMA}.export_audit_log FROM "{AUDIT_WRITER_ROLE}";'
    )


def downgrade() -> None:
    op.execute(
        f'REVOKE SELECT, INSERT ON {AUDIT_SCHEMA}.export_audit_log FROM "{AUDIT_WRITER_ROLE}";'
    )
    op.execute(f'REVOKE USAGE ON SCHEMA {AUDIT_SCHEMA} FROM "{AUDIT_WRITER_ROLE}";')

    op.drop_index(
        "ix_export_audit_log_correlation_id", table_name="export_audit_log", schema=AUDIT_SCHEMA
    )
    op.drop_column("export_audit_log", "metadata", schema=AUDIT_SCHEMA)
    op.drop_column("export_audit_log", "correlation_id", schema=AUDIT_SCHEMA)
    op.drop_column("export_audit_log", "target_id", schema=AUDIT_SCHEMA)
    op.drop_column("export_audit_log", "target_type", schema=AUDIT_SCHEMA)
    op.drop_column("export_audit_log", "action", schema=AUDIT_SCHEMA)
    op.drop_column("export_audit_log", "actor_id", schema=AUDIT_SCHEMA)
    op.drop_column("export_audit_log", "outcome", schema=AUDIT_SCHEMA)

    op.execute("ALTER TABLE analytics_audit.export_audit_log SET SCHEMA public;")
    op.execute(f"DROP SCHEMA IF EXISTS {AUDIT_SCHEMA};")
