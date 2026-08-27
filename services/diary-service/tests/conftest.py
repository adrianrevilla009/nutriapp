"""Session-scoped testcontainers-backed Postgres for integration and
contract tests (testing-strategy SKILL.md)."""

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


@pytest.fixture
async def db_engine(postgres_async_url):
    # Function-scoped deliberately -- see identity-service/tests/conftest.py
    # for the event-loop-binding rationale.
    engine = create_async_engine(postgres_async_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
