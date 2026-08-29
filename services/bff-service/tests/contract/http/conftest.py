"""Contract-test app: no database, no messaging (this service has
neither) -- just the dashboard/health routers wired against fake ports
(never a real diary-service/nutrition-calculation-service call, test-plan
section 2/3's explicit "never a live call" requirement). Authenticated
requests use a real signed RS256 JWT verified by a real JwtVerifier wired
against a fake (in-memory) JWKS HTTP client -- no real identity-service or
network call, but exercising the actual verification code path. Mirrors
every other service's identical conftest.py.
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

from infrastructure.http.health import router as health_router
from infrastructure.http.routes.dashboard_routes import router as dashboard_router
from tests.fixtures.factories import (
    FakeDiarySummaryPort,
    FakeNutritionTargetPort,
    FakeNutritionTotalsPort,
)

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()


class _CombinedNutritionCalculationFake:
    """Delegates to independent fake totals/target ports, mirroring
    NutritionCalculationServiceClient's real shape (one adapter class
    implementing both ports) for route-level wiring."""

    def __init__(
        self, totals_port: FakeNutritionTotalsPort, target_port: FakeNutritionTargetPort
    ) -> None:
        self._totals_port = totals_port
        self._target_port = target_port

    async def get_totals(self, total_date, authorization_header):
        return await self._totals_port.get_totals(total_date, authorization_header)

    async def get_target(self, authorization_header):
        return await self._target_port.get_target(authorization_header)


@dataclass
class _FakeContainer:
    diary_summary_client: FakeDiarySummaryPort
    nutrition_calculation_client: _CombinedNutritionCalculationFake
    jwt_verifier: object = field(init=False)

    def __post_init__(self) -> None:
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)


@pytest.fixture
def diary_port() -> FakeDiarySummaryPort:
    return FakeDiarySummaryPort()


@pytest.fixture
def totals_port() -> FakeNutritionTotalsPort:
    return FakeNutritionTotalsPort()


@pytest.fixture
def target_port() -> FakeNutritionTargetPort:
    return FakeNutritionTargetPort()


@pytest.fixture
def container(
    diary_port: FakeDiarySummaryPort,
    totals_port: FakeNutritionTotalsPort,
    target_port: FakeNutritionTargetPort,
) -> _FakeContainer:
    return _FakeContainer(
        diary_summary_client=diary_port,
        nutrition_calculation_client=_CombinedNutritionCalculationFake(totals_port, target_port),
    )


@pytest.fixture
async def app_client(container: _FakeContainer):
    app = FastAPI()
    app.include_router(dashboard_router)
    app.include_router(health_router)
    app.state.container = container

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    token = build_signed_token(_TEST_PRIVATE_KEY, user_id)
    return {"Authorization": f"Bearer {token}"}
