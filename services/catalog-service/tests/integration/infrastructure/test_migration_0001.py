"""Applies the real Alembic migration (not the ORM's create_all) against a
fresh testcontainers Postgres — validates the `pg_trgm` extension
creation risk flagged in the implementation plan section 7, at least for
the local/dev Postgres image."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture()
def alembic_config(postgres_container) -> Config:
    sync_url = postgres_container.get_connection_url()
    os.environ["CATALOG_SERVICE_DATABASE_URL"] = sync_url
    service_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    config = Config(os.path.join(service_root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(service_root, "migrations"))
    config.set_main_option("sqlalchemy.url", sync_url)
    return config


def test_migration_applies_cleanly_to_empty_database(alembic_config):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
