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
    # Function-scoped deliberately (see identity-service's conftest.py for
    # the full rationale: asyncpg pools are bound to the event loop they
    # were created on).
    engine = create_async_engine(postgres_async_url)
    async with engine.begin() as conn:
        # pg_trgm powers the typo-tolerant search path (ADR-0012) — must
        # exist before `create_all` if any column used `gin_trgm_ops`, and
        # is needed regardless for `similarity()` used by the search read
        # model's queries.
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        await conn.run_sync(Base.metadata.create_all)
        # `Base.metadata.create_all` renders `search_vector` as a real
        # `GENERATED ALWAYS AS (...) STORED` column (models.py's
        # `Computed(persisted=True)`) — identical in shape to
        # migrations/versions/0001_create_catalog_tables.py's raw SQL,
        # exercised verbatim by test_migration_0001.py. Only the indexes
        # (not expressed in the ORM model) need adding here.
        await conn.exec_driver_sql(
            "CREATE INDEX ix_products_search_vector ON products USING GIN (search_vector);"
        )
        await conn.exec_driver_sql(
            "CREATE INDEX ix_products_name_trgm ON products USING GIN (name gin_trgm_ops);"
        )
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
