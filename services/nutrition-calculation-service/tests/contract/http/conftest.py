"""Contract-test app: real Postgres (testcontainers) behind the routes, a
fake current-target/current-total cache swapped in via a fake Container so
these tests exercise real HTTP routing/serialization against a real DB
without needing Redis/RabbitMQ running (testing-strategy SKILL.md).
Authenticated requests use a real signed RS256 JWT verified by a real
JwtVerifier wired against a fake (in-memory) JWKS HTTP client -- no real
identity-service or network call, but exercising the actual verification
code path. Mirrors services/diary-service's identical conftest.py.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.nutrition_total_routes import router as nutrition_total_router
from infrastructure.http.routes.target_routes import router as target_router
from tests.fixtures.factories import FakeCurrentTargetCache, FakeCurrentTotalCache
from tests.fixtures.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()


class _FakeContainer:
    def __init__(self) -> None:
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)
        self.current_target_cache = FakeCurrentTargetCache()
        self.current_total_cache = FakeCurrentTotalCache()


@pytest.fixture
async def app_client(db_engine: AsyncEngine):
    app = FastAPI()
    app.include_router(target_router)
    app.include_router(nutrition_total_router)
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


def auth_headers(user_id: uuid.UUID) -> dict:
    token = build_signed_token(_TEST_PRIVATE_KEY, user_id)
    return {"Authorization": f"Bearer {token}"}
