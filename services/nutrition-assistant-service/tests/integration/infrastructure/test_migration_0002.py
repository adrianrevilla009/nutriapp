from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_migration_0002_applies_and_downgrades_cleanly(postgres_container) -> None:
    sync_url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)

    command.upgrade(cfg, "0002")

    engine = create_engine(sync_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "processed_entitlement_events" in tables
    # Migration 0001's tables are untouched (additive-only, per the
    # database-migrations SKILL.md's expand/contract pattern).
    assert "entitlement_cache" in tables

    command.downgrade(cfg, "0001")
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert "processed_entitlement_events" not in tables_after_downgrade
    assert "entitlement_cache" in tables_after_downgrade  # untouched by the downgrade

    command.downgrade(cfg, "base")
    engine.dispose()
