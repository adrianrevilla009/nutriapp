"""Runs the real Alembic migration chain (0001 -> 0002) against a fresh,
containerized Postgres (database-migrations SKILL.md: "Migrations are
tested against a real, containerized Postgres instance, not mocked") and
asserts:
  - `export_audit_log` genuinely moved into the `analytics_audit` schema.
  - the new audit-record columns exist.
  - `analytics_service_audit_writer` can INSERT/SELECT but not UPDATE/DELETE.

Mirrors identity-service's `test_migration_0001.py` precedent exactly,
adapted to a second migration on top of an already-applied first one --
0001 is treated as immutable/already-applied per this change's own
constraint (do not edit it), so this test starts from a fresh database and
runs the full 0001 -> 0002 chain, same as any real deploy would.
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
        # RDS master user (CREATEROLE) BEFORE the migration ever runs -- the
        # migration's own DB_ROLE does not have CREATEROLE and can only
        # GRANT/REVOKE privileges on a role that already exists. The
        # container's default user is effectively a superuser, standing in
        # for "master" here.
        import psycopg2

        with psycopg2.connect(sync_url.replace("postgresql+psycopg2", "postgresql")) as admin_conn:
            admin_conn.autocommit = True
            with admin_conn.cursor() as cur:
                cur.execute("CREATE ROLE analytics_service_audit_writer NOLOGIN;")

        cfg = Config(os.path.join(SERVICE_ROOT, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(SERVICE_ROOT, "migrations"))
        cfg.set_main_option("sqlalchemy.url", alembic_url)
        command.upgrade(cfg, "head")
        yield sync_url
        command.downgrade(cfg, "base")


async def test_migration_0002__export_audit_log_lives_in_analytics_audit_schema(
    migrated_sync_url,
):
    async_url = migrated_sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    engine = create_async_engine(async_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = 'export_audit_log'"
            )
        )
        schemas = {row[0] for row in result}
    await engine.dispose()
    assert schemas == {"analytics_audit"}


async def test_migration_0002__adds_mandatory_audit_columns(migrated_sync_url):
    async_url = migrated_sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    engine = create_async_engine(async_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'analytics_audit' AND table_name = 'export_audit_log'"
            )
        )
        columns = {row[0] for row in result}
    await engine.dispose()
    assert {
        "outcome",
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "correlation_id",
        "metadata",
    }.issubset(columns)


async def test_migration_0002__audit_writer_role_can_insert_but_not_update_or_delete(
    migrated_sync_url,
):
    async_url = migrated_sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    engine = create_async_engine(async_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee = 'analytics_service_audit_writer' "
                "AND table_schema = 'analytics_audit' AND table_name = 'export_audit_log'"
            )
        )
        privileges = {row[0] for row in result}
    await engine.dispose()
    assert privileges == {"SELECT", "INSERT"}
    assert "UPDATE" not in privileges
    assert "DELETE" not in privileges


async def test_migration_0002__downgrade_restores_public_schema_table(migrated_sync_url):
    async_url = migrated_sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    alembic_url = migrated_sync_url.replace("postgresql+psycopg2", "postgresql")

    cfg = Config(os.path.join(SERVICE_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(SERVICE_ROOT, "migrations"))
    cfg.set_main_option("sqlalchemy.url", alembic_url)
    command.downgrade(cfg, "0001")

    engine = create_async_engine(async_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = 'export_audit_log'"
            )
        )
        schemas = {row[0] for row in result}
    await engine.dispose()
    assert schemas == {"public"}

    # Restore to head so the module-scoped fixture's own final downgrade
    # (base) still runs cleanly regardless of test execution order.
    command.upgrade(cfg, "head")
