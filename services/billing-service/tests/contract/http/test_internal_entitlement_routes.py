"""GET /internal/v1/billing/entitlements/{user_id} -- test-plan section 3."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.subscription_status import SubscriptionStatus
from infrastructure.persistence.postgres_subscription_repository import (
    PostgresSubscriptionRepository,
)
from tests.contract.http.conftest import INTERNAL_ENTITLEMENT_CREDENTIAL
from tests.fixtures.factories import make_subscription


def _internal_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    headers["X-Internal-Service-Credential"] = INTERNAL_ENTITLEMENT_CREDENTIAL
    return headers


async def test_entitled_true_for_active_subscription(app_client, db_engine):
    client, _container = app_client
    user_id = uuid.uuid4()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        await repo.save(make_subscription(user_id=user_id, status=SubscriptionStatus.active()))
        await session.commit()

    response = await client.get(
        f"/internal/v1/billing/entitlements/{user_id}", headers=_internal_headers()
    )
    assert response.status_code == 200
    assert response.json()["entitled"] is True


async def test_entitled_false_for_no_subscription(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()

    response = await client.get(
        f"/internal/v1/billing/entitlements/{user_id}", headers=_internal_headers()
    )
    assert response.status_code == 200
    assert response.json()["entitled"] is False


async def test_missing_credential_rejected(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()

    response = await client.get(f"/internal/v1/billing/entitlements/{user_id}")
    assert response.status_code == 401


async def test_wrong_credential_rejected(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()
    headers: dict[str, str] = {}
    headers["X-Internal-Service-Credential"] = "wrong-credential"

    response = await client.get(f"/internal/v1/billing/entitlements/{user_id}", headers=headers)
    assert response.status_code == 401
