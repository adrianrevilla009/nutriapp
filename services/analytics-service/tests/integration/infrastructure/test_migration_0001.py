"""Applies the real Alembic migration (not the ORM's create_all) against a
fresh testcontainers Postgres -- both `upgrade`/`downgrade` paths
(database-migrations SKILL.md, test-plan section 3)."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture
def alembic_config(postgres_container, monkeypatch) -> Config:
    sync_url = postgres_container.get_connection_url()
    # `monkeypatch.setenv` (not a raw `os.environ[...] =`) so this process-
    # global env var is restored after the test -- migrations/env.py
    # unconditionally prefers ANALYTICS_SERVICE_DATABASE_URL over whatever
    # `sqlalchemy.url` a Config object was given, so a leaked value here
    # would silently redirect a *different* test file's migration run
    # (e.g. test_migration_0002.py's) at this container instead of its own.
    monkeypatch.setenv("ANALYTICS_SERVICE_DATABASE_URL", sync_url)
    service_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    config = Config(os.path.join(service_root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(service_root, "migrations"))
    config.set_main_option("sqlalchemy.url", sync_url)
    return config


def test_migration_applies_cleanly_to_empty_database(alembic_config):
    # Pinned to "0001" (not "head"): this test asserts THIS migration
    # applies/rolls back cleanly in isolation. "head" now includes 0002
    # (migrations/versions/0002_export_audit_log_compliance.py), which
    # depends on the `analytics_service_audit_writer` role already
    # existing (created out-of-band by the db-provision Job in real
    # deploys) -- covered by that migration's own dedicated test,
    # test_migration_0002.py, which sets that role up first.
    command.upgrade(alembic_config, "0001")
    command.downgrade(alembic_config, "base")
