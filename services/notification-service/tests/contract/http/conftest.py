"""Contract-test app: real Postgres (testcontainers) behind the routes.
Authenticated requests use a real signed RS256 JWT verified by a real
JwtVerifier wired against a fake (in-memory) JWKS HTTP client -- no real
identity-service or network call, but exercising the actual verification
code path. Mirrors every other service's identical conftest.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

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
from infrastructure.http.routes.preferences_routes import router as preferences_router
from infrastructure.http.routes.provider_webhook_routes import router as provider_webhook_router

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()


@dataclass
class _FakeContainer:
    jwt_verifier: object = field(init=False)

    def __post_init__(self) -> None:
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)


@pytest.fixture
def container() -> _FakeContainer:
    return _FakeContainer()


@pytest.fixture
async def app_client(db_engine: AsyncEngine, container: _FakeContainer):
    app = FastAPI()
    app.include_router(preferences_router)
    app.include_router(provider_webhook_router)
    app.include_router(health_router)

    app.state.container = container

    async def override_get_session():
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[deps.get_session] = override_get_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def auth_headers(user_id: uuid.UUID) -> dict:
    token = build_signed_token(_TEST_PRIVATE_KEY, user_id)
    return {"Authorization": f"Bearer {token}"}
