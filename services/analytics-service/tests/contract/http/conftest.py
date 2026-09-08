"""Contract-test app: real Postgres (testcontainers) behind the routes, a
fake `EntitlementCheckPort` swapped in via dependency overrides. Real
signed RS256 JWT verified by a real `JwtVerifier` wired against a fake
JWKS HTTP client -- mirrors social-service's/recipe-service's identical
precedent."""

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
from infrastructure.http.routes.report_routes import router as report_router
from infrastructure.http.routes.trend_routes import router as trend_router
from tests.fixtures.factories import FakeEntitlementCheckPort

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()
_CONTRACT_ROUTERS = (trend_router, report_router, health_router)


class _FakeContainer:
    def __init__(self, db_engine: AsyncEngine) -> None:
        self.entitlement_check = FakeEntitlementCheckPort()
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)
        self._db_engine = db_engine

    def new_audit_session(self) -> AsyncSession:
        # Contract tests exercise `report_routes.py` end-to-end (real
        # Postgres via `db_engine`, not a fake) -- there is no separate
        # AUDIT_WRITER_ROLE-restricted engine in this fixture (that
        # genuinely-restricted-connection behavior is proven by
        # tests/integration/infrastructure/test_postgres_export_audit_repository.py
        # instead); this just needs its own session object so
        # report_routes.py's `finally: await audit_session.close()` and
        # independent `.commit()` semantics work the same as in production.
        return AsyncSession(self._db_engine, expire_on_commit=False)


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
    container = _FakeContainer(db_engine)
    app = _build_app(container, db_engine)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, container


def auth_headers(user_id: uuid.UUID) -> dict:
    token = build_signed_token(_TEST_PRIVATE_KEY, user_id)
    return {"Authorization": f"Bearer {token}"}
