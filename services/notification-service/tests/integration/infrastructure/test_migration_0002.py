"""Applying migration 0002 on top of 0001 succeeds and produces the
expected pending_push_dispatch table (mirrors test_migration_0001.py's
shape)."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_TABLES = {
    "reminder_schedule",
    "processed_notifications",
    "delivery_log",
    "suppression_list",
    "notification_preferences",
    "pending_push_dispatch",
}


def test_migration_0002_applies_cleanly_on_top_of_0001(postgres_container):
    sync_url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql")

    config = Config()
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(config, "0002")

    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert EXPECTED_TABLES.issubset(table_names)
        columns = {col["name"] for col in inspector.get_columns("pending_push_dispatch")}
        assert {
            "dispatch_id",
            "user_id",
            "category",
            "template_name",
            "template_version",
            "context",
            "correlation_id",
            "earliest_dispatch_at",
            "status",
        }.issubset(columns)
    finally:
        command.downgrade(config, "base")
        engine.dispose()
