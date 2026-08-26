"""Contract-test app: real Postgres (testcontainers) behind the routes, a
fake Redis-backed search cache swapped in via dependency overrides so
these tests exercise real HTTP routing/serialization against a real DB
without needing RabbitMQ/Redis running (testing-strategy SKILL.md)."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.product_routes import router as product_router
from infrastructure.http.routes.search_routes import router as search_router
from tests.fixtures.factories import FakeSearchCache


class _FakeContainer:
    def __init__(self) -> None:
        self.search_cache = FakeSearchCache()


@pytest.fixture()
async def app_client(db_engine: AsyncEngine):
    app = FastAPI()
    app.include_router(search_router)
    app.include_router(product_router)
    app.include_router(health_router)

    container = _FakeContainer()
    app.state.container = container

    async def override_get_session():
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_container] = lambda: container

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
