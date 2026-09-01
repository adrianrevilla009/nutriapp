"""Contract tests for GET/PATCH /api/v1/notifications/preferences
(test-plan section 3)."""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_get_preferences_returns_defaults_for_a_valid_jwt(app_client):
    user_id = uuid.uuid4()
    response = await app_client.get(
        "/api/v1/notifications/preferences", headers=auth_headers(user_id)
    )
    assert response.status_code == 200
    body = response.json()
    categories = {item["category"] for item in body["preferences"]}
    assert categories == {"fasting", "meal", "water", "new_follower"}


async def test_get_preferences_requires_authentication(app_client):
    response = await app_client.get("/api/v1/notifications/preferences")
    assert response.status_code == 401


async def test_patch_preferences_valid_update(app_client):
    user_id = uuid.uuid4()
    response = await app_client.patch(
        "/api/v1/notifications/preferences",
        headers=auth_headers(user_id),
        json={
            "category": "water",
            "push_enabled": False,
            "quiet_hours_start": "23:00:00",
            "quiet_hours_end": "07:00:00",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 200
    assert response.json()["push_enabled"] is False


async def test_patch_preferences_invalid_category_is_422(app_client):
    user_id = uuid.uuid4()
    response = await app_client.patch(
        "/api/v1/notifications/preferences",
        headers=auth_headers(user_id),
        json={
            "category": "verification",
            "push_enabled": True,
            "quiet_hours_start": "22:00:00",
            "quiet_hours_end": "08:00:00",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 422


async def test_patch_preferences_malformed_quiet_hours_is_422(app_client):
    user_id = uuid.uuid4()
    response = await app_client.patch(
        "/api/v1/notifications/preferences",
        headers=auth_headers(user_id),
        json={
            "category": "meal",
            "push_enabled": True,
            "quiet_hours_start": "09:00:00",
            "quiet_hours_end": "09:00:00",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 422


async def test_patch_preferences_requires_authentication(app_client):
    response = await app_client.patch(
        "/api/v1/notifications/preferences",
        json={
            "category": "meal",
            "push_enabled": True,
            "quiet_hours_start": "22:00:00",
            "quiet_hours_end": "08:00:00",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 401
