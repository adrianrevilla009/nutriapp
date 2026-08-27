"""Contract-test app: real Postgres (testcontainers) behind the routes,
fake password hasher / rate limiter / token issuer swapped in via
dependency overrides so these tests exercise real HTTP routing/
serialization against a real DB without needing Redis/RabbitMQ running
(testing-strategy SKILL.md).
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.auth_routes import router as auth_router
from infrastructure.http.routes.internal_token_routes import router as internal_router
from infrastructure.http.routes.jwks_routes import router as jwks_router
from infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from infrastructure.security.jwt_token_issuer import JwtTokenIssuer, generate_rsa_key_pair
from tests.fixtures.fakes import FakeRateLimiter

INTERNAL_CREDENTIAL = "test-internal-credential"


class _FakeSettings:
    internal_reveal_credential = INTERNAL_CREDENTIAL


class _FakeContainer:
    def __init__(self) -> None:
        self.password_hasher = Argon2PasswordHasher()
        private_pem, public_pem = generate_rsa_key_pair()
        self.token_issuer = JwtTokenIssuer(private_pem, public_pem, key_id="test-key-1")
        self.rate_limiter = FakeRateLimiter()
        self.settings = _FakeSettings()


@pytest.fixture
async def app_client(db_engine: AsyncEngine):
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(jwks_router)
    app.include_router(internal_router)
    app.include_router(health_router)

    container = _FakeContainer()
    app.state.container = container

    async def override_get_session():
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    async def override_get_audit_session():
        # Contract tests exercise HTTP routing/serialization, not
        # privilege enforcement (that's covered by
        # tests/integration/infrastructure/test_postgres_audit_repository.py
        # against a real Job-provisioned role) — reusing the same
        # unrestricted db_engine here is intentional and sufficient.
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_audit_session] = override_get_audit_session
    app.dependency_overrides[deps.get_container] = lambda: container

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
