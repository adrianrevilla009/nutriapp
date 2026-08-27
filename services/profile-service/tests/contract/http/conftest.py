"""Contract-test app: real Postgres (testcontainers) behind the routes,
a fake DataEncryptionPort swapped in via dependency overrides so these
tests exercise real HTTP routing/serialization against a real DB without
needing AWS KMS/RabbitMQ running (testing-strategy SKILL.md). Authenticated
requests use a real signed RS256 JWT verified by a real JwtVerifier wired
against a fake (in-memory) JWKS HTTP client -- no real identity-service or
network call, but exercising the actual verification code path.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from domain.entities.profile import Profile
from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.consent_routes import router as consent_router
from infrastructure.http.routes.profile_routes import router as profile_router
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from tests.fixtures.factories import FakeDataEncryption
from tests.fixtures.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()


class _FakeContainer:
    def __init__(self) -> None:
        self.encryption = FakeDataEncryption()
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)


@pytest.fixture
async def app_client(db_engine: AsyncEngine):
    app = FastAPI()
    app.include_router(profile_router)
    app.include_router(consent_router)
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


@pytest.fixture
async def seeded_user(db_engine: AsyncEngine):
    """A user_id with an already-created (but not yet consented) profile --
    mirrors what the UserRegistered consumer would have produced."""
    user_id = uuid.uuid4()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        event_store = PostgresEventStore(session)
        _profile, event = Profile.create(user_id, correlation_id="corr-seed")
        await event_store.append(event)
        await session.commit()
    return user_id


def auth_headers(user_id: uuid.UUID) -> dict:
    token = build_signed_token(_TEST_PRIVATE_KEY, user_id)
    return {"Authorization": f"Bearer {token}"}
