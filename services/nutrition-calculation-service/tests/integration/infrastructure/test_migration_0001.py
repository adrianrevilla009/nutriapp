"""Applying migration 0001 to an empty database succeeds and produces the
expected tables (test-plan section 2)."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_TABLES = {
    "nutrition_targets",
    "nutrition_target_history",
    "daily_nutrition_totals",
    "nutrient_panel_mirror",
    "user_metrics_snapshot",
    "outbox",
    "processed_events",
}


def test_migration_0001_applies_cleanly(postgres_container):
    sync_url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql")

    config = Config()
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(config, "0001")

    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert EXPECTED_TABLES.issubset(table_names)
    finally:
        command.downgrade(config, "base")
        engine.dispose()
