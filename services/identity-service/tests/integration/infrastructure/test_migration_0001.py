"""Runs the real Alembic migration against a fresh, containerized
Postgres (database-migrations SKILL.md: "Migrations are tested against a
real, containerized Postgres instance, not mocked") and asserts the
append-only audit_log role grants it creates.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer

SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


@pytest.fixture(scope="module")
def migrated_sync_url():
    with PostgresContainer("postgres:16-alpine") as pg:
        sync_url = pg.get_connection_url()  # postgresql+psycopg2://...
        alembic_url = sync_url.replace("postgresql+psycopg2", "postgresql")

        # Simulates infra/k8s/charts/_lib/templates/_db-provision-job.tpl's
        # audit-writer role creation, which in real deployment runs as the
        # RDS master user (CREATEROLE) BEFORE the migration ever runs — the
        # migration's own DB_ROLE does not have CREATEROLE and can only
        # GRANT/REVOKE privileges on a role that already exists. The
        # container's default user is effectively a superuser, standing in
        # for "master" here.
        import psycopg2

        with psycopg2.connect(sync_url.replace("postgresql+psycopg2", "postgresql")) as admin_conn:
            admin_conn.autocommit = True
            with admin_conn.cursor() as cur:
                cur.execute("CREATE ROLE identity_service_audit_writer NOLOGIN;")

        cfg = Config(os.path.join(SERVICE_ROOT, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(SERVICE_ROOT, "migrations"))
        cfg.set_main_option("sqlalchemy.url", alembic_url)
        command.upgrade(cfg, "head")
        yield sync_url


async def test_migration_0001__creates_all_expected_tables(migrated_sync_url):
    async_url = migrated_sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    engine = create_async_engine(async_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        )
        tables = {row[0] for row in result}
    await engine.dispose()
    assert tables == {
        "alembic_version",
        "audit_log",
        "email_verification_tokens",
        "outbox",
        "password_reset_tokens",
        "refresh_tokens",
        "users",
    }


async def test_migration_0001__audit_writer_role_can_insert_but_not_update_or_delete(
    migrated_sync_url,
):
    async_url = migrated_sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    engine = create_async_engine(async_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee = 'identity_service_audit_writer' AND table_name = 'audit_log'"
            )
        )
        privileges = {row[0] for row in result}
    await engine.dispose()
    assert privileges == {"INSERT"}
    assert "UPDATE" not in privileges
    assert "DELETE" not in privileges
