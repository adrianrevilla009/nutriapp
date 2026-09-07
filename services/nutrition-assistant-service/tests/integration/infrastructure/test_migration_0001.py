from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_migration_0001_applies_and_downgrades_cleanly(postgres_container) -> None:
    sync_url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)

    command.upgrade(cfg, "0001")

    engine = create_engine(sync_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for expected in (
        "food_entry_history",
        "water_intake_history",
        "nutrition_value_history",
        "nutrition_target_history",
        "analytics_signal_history",
        "entitlement_cache",
        "processed_diary_events",
        "processed_nutrition_calculation_events",
        "processed_analytics_events",
        "chat_audit_log",
        "outbox",
    ):
        assert expected in tables

    command.downgrade(cfg, "base")
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert "food_entry_history" not in tables_after_downgrade
    engine.dispose()
