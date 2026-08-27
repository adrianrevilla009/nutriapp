"""End-to-end (within this service) happy-path flow through the real HTTP
routes and real Postgres: register -> reveal verification secret (as
notification-service would) -> verify-email -> login -> refresh -> logout,
plus the password-reset variant. This is the fixture referenced in the
test plan section 4 for reuse once catalog/diary/nutrition-calculation
services exist.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.persistence.models import EmailVerificationTokenModel, PasswordResetTokenModel
from tests.contract.http.conftest import INTERNAL_CREDENTIAL

VALID_PASSWORD = "Str0ng!Passw0rd"


async def _latest_reference_id(db_engine: AsyncEngine, model, email_local_hint: str) -> str:
    async with AsyncSession(db_engine) as session:
        result = await session.execute(select(model).order_by(model.created_at.desc()))
        row = result.scalars().first()
        return str(row.reference_id)


async def test_full_flow__register_verify_login_refresh_logout(app_client, db_engine: AsyncEngine):
    register_response = await app_client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "password": VALID_PASSWORD},
    )
    assert register_response.status_code in (200, 201)

    reference_id = await _latest_reference_id(
        db_engine, EmailVerificationTokenModel, "flow@example.com"
    )
    reveal_response = await app_client.post(
        f"/internal/v1/auth/tokens/{reference_id}/reveal",
        headers={"X-Internal-Service-Credential": INTERNAL_CREDENTIAL},
    )
    assert reveal_response.status_code == 200
    secret = reveal_response.json()["secret"]

    verify_response = await app_client.post(
        "/api/v1/auth/verify-email", json={"reference_id": reference_id, "secret": secret}
    )
    assert verify_response.status_code == 200

    # The reveal endpoint is single-use.
    replay_response = await app_client.post(
        f"/internal/v1/auth/tokens/{reference_id}/reveal",
        headers={"X-Internal-Service-Credential": INTERNAL_CREDENTIAL},
    )
    assert replay_response.status_code == 400

    login_response = await app_client.post(
        "/api/v1/auth/login", json={"email": "flow@example.com", "password": VALID_PASSWORD}
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    refresh_response = await app_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]

    logout_response = await app_client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["revoked"] is True

    # A revoked refresh token can no longer be exchanged.
    post_logout_refresh = await app_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert post_logout_refresh.status_code == 401


async def test_full_flow__password_reset_via_reveal_and_confirm(app_client, db_engine: AsyncEngine):
    await app_client.post(
        "/api/v1/auth/register", json={"email": "resetflow@example.com", "password": VALID_PASSWORD}
    )
    reference_id = await _latest_reference_id(
        db_engine, EmailVerificationTokenModel, "resetflow@example.com"
    )
    reveal = await app_client.post(
        f"/internal/v1/auth/tokens/{reference_id}/reveal",
        headers={"X-Internal-Service-Credential": INTERNAL_CREDENTIAL},
    )
    await app_client.post(
        "/api/v1/auth/verify-email",
        json={"reference_id": reference_id, "secret": reveal.json()["secret"]},
    )

    reset_request = await app_client.post(
        "/api/v1/auth/password-reset/request", json={"email": "resetflow@example.com"}
    )
    assert reset_request.status_code == 202

    reset_reference_id = await _latest_reference_id(
        db_engine, PasswordResetTokenModel, "resetflow@example.com"
    )
    reset_reveal = await app_client.post(
        f"/internal/v1/auth/tokens/{reset_reference_id}/reveal",
        headers={"X-Internal-Service-Credential": INTERNAL_CREDENTIAL},
    )
    assert reset_reveal.status_code == 200

    new_password = "Ev3nStr0nger!Passw0rd"
    confirm_response = await app_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "reference_id": reset_reference_id,
            "secret": reset_reveal.json()["secret"],
            "new_password": new_password,
        },
    )
    assert confirm_response.status_code == 200

    old_password_login = await app_client.post(
        "/api/v1/auth/login", json={"email": "resetflow@example.com", "password": VALID_PASSWORD}
    )
    assert old_password_login.status_code == 401

    new_password_login = await app_client.post(
        "/api/v1/auth/login", json={"email": "resetflow@example.com", "password": new_password}
    )
    assert new_password_login.status_code == 200
