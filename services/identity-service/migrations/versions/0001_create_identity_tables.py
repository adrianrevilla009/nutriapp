"""Create identity-service tables: users, refresh_tokens,
email_verification_tokens, password_reset_tokens, outbox, audit_log.

CREATE TABLE-only — additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate.

Also grants INSERT-only privileges on audit_log to a dedicated
`identity_service_audit_writer` role (observability-audit SKILL.md:
"the DB role backing this table can INSERT but not UPDATE/DELETE"). Role
creation is idempotent (DO $$ ... EXCEPTION guard) so this migration is
safe to run against a fresh database provisioned by the `_db-provision-job`
Helm hook (platform-infra plan section 9.1).

Revision ID: 0001
Revises:
Create Date: 2026-08-24

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
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("roles", postgresql.ARRAY(sa.String(16)), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "known_device_fingerprints",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    for table_name in ("email_verification_tokens", "password_reset_tokens"):
        op.create_table(
            table_name,
            sa.Column("reference_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("secret_hash", sa.String(128), nullable=False),
            sa.Column("raw_secret", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revealed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(f"ix_{table_name}_user_id", table_name, ["user_id"])

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

    op.create_table(
        "audit_log",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_log_target", "audit_log", ["target_type", "target_id"])

    # Append-only audit trail: dedicated role can INSERT but never
    # UPDATE/DELETE audit_log (observability-audit SKILL.md). The role
    # itself is created by infra/k8s/charts/_lib/templates/_db-provision-job.tpl,
    # which runs as the RDS master user (CREATEROLE) — this migration runs
    # as this service's own DB_ROLE, which does NOT have CREATEROLE, but
    # DOES own audit_log (it created the table above) and can therefore
    # GRANT/REVOKE privileges on it to any already-existing role without
    # needing CREATEROLE. If this GRANT fails with "role does not exist",
    # the provisioning Job did not run first — that ordering is mandatory,
    # not optional (see that template's own header comment).
    op.execute("GRANT INSERT ON audit_log TO identity_service_audit_writer;")
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM identity_service_audit_writer;")


def downgrade() -> None:
    op.execute("REVOKE INSERT ON audit_log FROM identity_service_audit_writer;")
    op.drop_index("ix_audit_log_target", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    for table_name in ("password_reset_tokens", "email_verification_tokens"):
        op.drop_index(f"ix_{table_name}_user_id", table_name=table_name)
        op.drop_table(table_name)
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
