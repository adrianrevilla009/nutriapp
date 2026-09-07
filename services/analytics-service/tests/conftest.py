"""Testcontainers-backed Postgres fixtures backing analytics-service's
integration and contract suites (testing-strategy SKILL.md)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.postgres import PostgresContainer

from infrastructure.persistence.models import Base

_POSTGRES_IMAGE = "postgres:16-alpine"


def _as_asyncpg_dsn(psycopg2_dsn: str) -> str:
    return psycopg2_dsn.replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    with PostgresContainer(_POSTGRES_IMAGE) as container:
        yield container


@pytest.fixture(scope="session")
def postgres_async_url(postgres_container: PostgresContainer) -> str:
    return _as_asyncpg_dsn(postgres_container.get_connection_url())


@pytest.fixture
async def db_engine(postgres_async_url: str) -> AsyncEngine:
    engine = create_async_engine(postgres_async_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()
