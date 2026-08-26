"""Session-scoped testcontainers-backed Postgres/Redis for integration and
contract tests (testing-strategy SKILL.md: "Use testcontainers to spin up
real Postgres/Redis instances scoped to the test session")."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

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
    # Function-scoped deliberately: asyncpg pools are bound to the event
    # loop they were created on, and pytest-asyncio creates a fresh loop
    # per test by default -- mirrors catalog-service's/diary-service's
    # identical conftest.py precedent.
    engine = create_async_engine(postgres_async_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as redis_c:
        yield redis_c


@pytest.fixture()
def redis_url(redis_container) -> str:
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"
