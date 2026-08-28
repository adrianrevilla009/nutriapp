"""Contract-test app: real Postgres (testcontainers) behind the routes, a
fake vision/catalog-lookup/barcode-decoder swapped in via a fake Container
so these tests exercise real HTTP routing/serialization against a real DB
without needing RabbitMQ running or a live Claude/catalog-service call.
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
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.recognition_routes import router as recognition_router
from tests.fixtures.factories import (
    FakeBarcodeDecoderPort,
    FakeCatalogLookupPort,
    FakeVisionRecognitionPort,
)
from shared_contracts.testing.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()


@dataclass
class _FakeSettings:
    confidence_threshold: float = 0.6
    photo_analysis_enabled: bool = True


@dataclass
class _FakeContainer:
    vision_adapter: FakeVisionRecognitionPort = field(default_factory=FakeVisionRecognitionPort)
    catalog_lookup_client: FakeCatalogLookupPort = field(default_factory=FakeCatalogLookupPort)
    barcode_decoder: FakeBarcodeDecoderPort = field(default_factory=FakeBarcodeDecoderPort)
    settings: _FakeSettings = field(default_factory=_FakeSettings)

    def __post_init__(self) -> None:
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)


@pytest.fixture
def container() -> _FakeContainer:
    return _FakeContainer()


@pytest.fixture
async def app_client(db_engine: AsyncEngine, container: _FakeContainer):
    app = FastAPI()
    app.include_router(recognition_router)
    app.include_router(health_router)

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
