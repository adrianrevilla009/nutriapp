"""Contract/integration tests: POST /internal/v1/profile/{user_id}/reveal-metrics
against real (testcontainers) Postgres, with a fake DataEncryptionPort and
a fake RateLimiterPort swapped in (implementation plan Addendum 2,
test-plan Addendum 2). Exercises real HTTP routing/serialization and the
real PostgresAuditRepository/PostgresSnapshotProjector adapters.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from structlog.testing import capture_logs

from infrastructure.http import dependencies as deps
from infrastructure.http.routes.internal_reveal_metrics_routes import (
    router as internal_reveal_metrics_router,
)
from infrastructure.persistence.models import ProfileSnapshotModel
from tests.fixtures.factories import FakeDataEncryption, FakeRateLimiter

VALID_CREDENTIAL = "nutrition-calc-test-credential"


@dataclass
class _FakeSettings:
    reveal_caller_credentials: dict = field(
        default_factory=lambda: {VALID_CREDENTIAL: "nutrition-calculation-service"}
    )
    reveal_rate_limit: int = 5
    reveal_rate_limit_window_seconds: int = 60


class _FakeContainer:
    def __init__(self) -> None:
        self.encryption = FakeDataEncryption()
        self.rate_limiter = FakeRateLimiter()
        self.settings = _FakeSettings()


@pytest.fixture()
async def internal_app_client(db_engine: AsyncEngine):
    app = FastAPI()
    app.include_router(internal_reveal_metrics_router)

    container = _FakeContainer()
    app.state.container = container

    async def override_get_session():
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    async def override_get_audit_session():
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_audit_session] = override_get_audit_session
    app.dependency_overrides[deps.get_container] = lambda: container

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.container = container  # type: ignore[attr-defined]
        yield client


@pytest.fixture()
async def seeded_snapshot_user(db_engine: AsyncEngine):
    """Seeds a profile_snapshot row directly (this suite tests the
    reveal-metrics route/query, not the projector -- projector-replay
    correctness has its own dedicated test)."""
    user_id = uuid.uuid4()
    encryption = FakeDataEncryption()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        row = ProfileSnapshotModel(
            user_id=user_id,
            consent_granted=True,
            weight_kg=await encryption.encrypt(user_id, "88.0"),
            height_cm=await encryption.encrypt(user_id, "175.0"),
            age=await encryption.encrypt(user_id, "40"),
            sex=await encryption.encrypt(user_id, "FEMALE"),
            activity_level=await encryption.encrypt(user_id, "LIGHT"),
            goal_type="MAINTAIN",
            goal_target_value=None,
            goal_target_date=None,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.commit()
    return user_id


def _reveal_url(user_id: uuid.UUID) -> str:
    return f"/internal/v1/profile/{user_id}/reveal-metrics"


async def test_correct_credential_returns_200_with_exactly_six_fields(
    internal_app_client, seeded_snapshot_user
):
    response = await internal_app_client.post(
        _reveal_url(seeded_snapshot_user),
        headers={"X-Internal-Service-Credential": VALID_CREDENTIAL},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "weight_kg",
        "height_cm",
        "age",
        "sex",
        "activity_level",
        "goal_type",
    }
    assert body["weight_kg"] == 88.0
    assert body["sex"] == "FEMALE"
    assert body["goal_type"] == "MAINTAIN"


async def test_missing_credential_returns_401_with_no_biometric_data(
    internal_app_client, seeded_snapshot_user
):
    response = await internal_app_client.post(_reveal_url(seeded_snapshot_user))
    assert response.status_code == 401
    body = response.json()
    assert "weight_kg" not in body
    assert body["code"] == "INVALID_CALLER_CREDENTIAL"


async def test_wrong_credential_returns_401_with_no_biometric_data(
    internal_app_client, seeded_snapshot_user
):
    response = await internal_app_client.post(
        _reveal_url(seeded_snapshot_user),
        headers={"X-Internal-Service-Credential": "not-the-right-one"},
    )
    assert response.status_code == 401
    assert "weight_kg" not in response.json()


async def test_unknown_user_id_returns_404(internal_app_client):
    response = await internal_app_client.post(
        _reveal_url(uuid.uuid4()),
        headers={"X-Internal-Service-Credential": VALID_CREDENTIAL},
    )
    assert response.status_code == 404


async def test_rate_limit_exceeded_returns_429_and_never_invokes_encryption(
    internal_app_client, seeded_snapshot_user
):
    container: _FakeContainer = internal_app_client.container  # type: ignore[attr-defined]
    for _ in range(container.settings.reveal_rate_limit):
        response = await internal_app_client.post(
            _reveal_url(seeded_snapshot_user),
            headers={"X-Internal-Service-Credential": VALID_CREDENTIAL},
        )
        assert response.status_code == 200

    container.encryption.decrypt_calls.clear()
    response = await internal_app_client.post(
        _reveal_url(seeded_snapshot_user),
        headers={"X-Internal-Service-Credential": VALID_CREDENTIAL},
    )
    assert response.status_code == 429
    assert container.encryption.decrypt_calls == []


async def test_log_redaction__successful_reveal_never_logs_a_biometric_value(
    internal_app_client, seeded_snapshot_user
):
    """Requirement 7: structured logs may record that a reveal occurred
    and which field NAMES were requested, never a numeric/enum VALUE."""
    with capture_logs() as captured:
        response = await internal_app_client.post(
            _reveal_url(seeded_snapshot_user),
            headers={"X-Internal-Service-Credential": VALID_CREDENTIAL},
        )
    assert response.status_code == 200

    forbidden_values = {"88.0", "175.0", "40", "FEMALE", "LIGHT", "MAINTAIN", 88.0, 175.0, 40}
    for entry in captured:
        for key, value in entry.items():
            if key == "fields":
                # Field NAMES are explicitly allowed.
                assert set(value) <= {
                    "weight_kg",
                    "height_cm",
                    "age",
                    "sex",
                    "activity_level",
                    "goal_type",
                }
                continue
            assert value not in forbidden_values, (
                f"Log entry leaked a biometric value via key={key!r}: {value!r}"
            )
