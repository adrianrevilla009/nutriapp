"""POST /api/v1/billing/checkout-sessions -- test-plan section 3."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.postgres_subscription_repository import (
    PostgresSubscriptionRepository,
)
from tests.contract.http.conftest import auth_headers
from tests.fixtures.factories import make_subscription


async def test_creates_checkout_session_for_authenticated_user(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()
    response = await client.post(
        "/api/v1/billing/checkout-sessions",
        json=dict(
            success_url="https://app.nutriapp.example/success",
            cancel_url="https://app.nutriapp.example/cancel",
        ),
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["checkout_url"].startswith("https://checkout.stripe.com/")


async def test_rejects_when_already_active(app_client, db_engine):
    client, _container = app_client
    user_id = uuid.uuid4()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        await repo.save(make_subscription(user_id=user_id))
        await session.commit()

    response = await client.post(
        "/api/v1/billing/checkout-sessions",
        json=dict(
            success_url="https://app.nutriapp.example/success",
            cancel_url="https://app.nutriapp.example/cancel",
        ),
        headers=auth_headers(user_id),
    )
    assert response.status_code == 409


async def test_unauthenticated_request_rejected(app_client):
    client, _container = app_client
    response = await client.post(
        "/api/v1/billing/checkout-sessions",
        json=dict(
            success_url="https://app.nutriapp.example/success",
            cancel_url="https://app.nutriapp.example/cancel",
        ),
    )
    assert response.status_code == 401
