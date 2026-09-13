from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_migration_0003_applies_and_downgrades_cleanly(postgres_container) -> None:
    sync_url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)

    command.upgrade(cfg, "0003")

    engine = create_engine(sync_url)
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("chat_audit_log")}
    assert "health_adjacent_flagged" in columns
    # Migration 0001/0002's tables/columns are untouched (additive-only,
    # per the database-migrations SKILL.md's expand/contract pattern).
    assert "disclaimer_included" in columns
    assert "processed_entitlement_events" in set(inspector.get_table_names())

    command.downgrade(cfg, "0002")
    columns_after_downgrade = {col["name"] for col in inspect(engine).get_columns("chat_audit_log")}
    assert "health_adjacent_flagged" not in columns_after_downgrade
    assert "disclaimer_included" in columns_after_downgrade  # untouched by the downgrade

    command.downgrade(cfg, "base")
    engine.dispose()
