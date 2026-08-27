"""Contract-test app: real Postgres (testcontainers) behind the routes, a
fake DailySummaryCachePort swapped in via a fake Container so these tests
exercise real HTTP routing/serialization against a real DB without
needing Redis/RabbitMQ running (testing-strategy SKILL.md). Authenticated
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

from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.daily_summary_routes import router as daily_summary_router
from infrastructure.http.routes.fasting_window_routes import router as fasting_window_router
from infrastructure.http.routes.food_entry_routes import router as food_entry_router
from infrastructure.http.routes.meal_plan_routes import router as meal_plan_router
from infrastructure.http.routes.water_intake_routes import router as water_intake_router
from infrastructure.messaging.diary_event_projector_consumer import apply_event_to_read_models
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from tests.fixtures.factories import FakeDailySummaryCachePort
from tests.fixtures.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()


class _FakeContainer:
    def __init__(self) -> None:
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)
        self.daily_summary_cache = FakeDailySummaryCachePort()


@pytest.fixture
async def app_client(db_engine: AsyncEngine):
    app = FastAPI()
    app.include_router(food_entry_router)
    app.include_router(water_intake_router)
    app.include_router(fasting_window_router)
    app.include_router(meal_plan_router)
    app.include_router(daily_summary_router)
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


async def project_pending_outbox_events(db_engine: AsyncEngine) -> None:
    """Simulates the async diary_event_projector_consumer having drained
    the outbox (implementation plan section 9.1: read models are updated
    asynchronously, not synchronously with the command's HTTP response) --
    used by contract tests for the GET/list endpoints, which are
    eventually consistent by design, without needing a live RabbitMQ
    container in every HTTP contract test."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        outbox = PostgresOutboxRepository(session)
        pending = await outbox.fetch_unpublished(limit=1000)
        for event in pending:
            await apply_event_to_read_models(session, event, redis_cache=None)
            await outbox.mark_published(event.event_id)
        await session.commit()
