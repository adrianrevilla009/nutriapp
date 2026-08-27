"""Alembic migration 0001 applies cleanly to an empty database
(test-plan section 2)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


@pytest.fixture()
def service_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def test_alembic_upgrade_head_applies_cleanly(postgres_container, service_dir):
    sync_url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql")
    env = dict(os.environ)
    env["DIARY_SERVICE_DATABASE_URL"] = sync_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=service_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    # Downgrade back to empty, so this test doesn't leak schema state into
    # the session-scoped postgres_container used by other test modules.
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=service_dir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
