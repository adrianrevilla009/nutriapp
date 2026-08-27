"""Session-scoped testcontainers-backed Postgres for integration and
contract tests (testing-strategy SKILL.md: "Use testcontainers to spin up
real Postgres/RabbitMQ/Redis instances scoped to the test session").
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer

from infrastructure.persistence.models import Base


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def postgres_async_url(postgres_container) -> str:
    sync_url = postgres_container.get_connection_url()
    return sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest.fixture()
async def db_engine(postgres_async_url):
    # Function-scoped (not session-scoped) deliberately: pytest-asyncio
    # gives each test function its own event loop by default, and asyncpg
    # connections/pools are bound to the loop they were created on — a
    # session-scoped engine would be created in one loop and then used
    # from another, raising "attached to a different loop". Creating (and
    # tearing down) the schema per test keeps each test fully isolated at
    # a modest, acceptable cost given the table count here.
    engine = create_async_engine(postgres_async_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
