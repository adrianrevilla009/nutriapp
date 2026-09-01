"""Contract-test app: real Postgres (testcontainers) behind the routes, a
fake `EntitlementCheckPort` swapped in via dependency overrides so these
tests exercise real HTTP routing/serialization against a real DB without
needing a live billing-service or RabbitMQ (testing-strategy SKILL.md).
Authenticated requests use a real signed RS256 JWT verified by a real
`JwtVerifier` wired against a fake (in-memory) JWKS HTTP client -- no real
identity-service or network call, but exercising the actual verification
code path (mirrors recipe-service's/billing-service's identical
precedent)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI
from shared_contracts.testing.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.feed_routes import router as feed_router
from infrastructure.http.routes.follow_routes import router as follow_router
from tests.fixtures.factories import FakeEntitlementCheckPort

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()
_CONTRACT_ROUTERS = (follow_router, feed_router, health_router)


class _FakeContainer:
    def __init__(self) -> None:
        self.entitlement_check = FakeEntitlementCheckPort()
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)


def _build_app(container: _FakeContainer, db_engine: AsyncEngine) -> FastAPI:
    app = FastAPI()
    for router in _CONTRACT_ROUTERS:
        app.include_router(router)
    app.state.container = container

    async def override_get_session():
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_container] = lambda: container
    return app


@pytest.fixture
async def app_client(db_engine: AsyncEngine):
    container = _FakeContainer()
    app = _build_app(container, db_engine)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, container


def auth_headers(user_id: uuid.UUID) -> dict:
    token = build_signed_token(_TEST_PRIVATE_KEY, user_id)
    return {"Authorization": f"Bearer {token}"}
