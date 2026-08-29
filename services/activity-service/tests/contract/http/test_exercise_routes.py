"""Contract tests for the four /api/v1/activity/exercises routes
(test-plan section 3)."""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_post_valid_payload_returns_201(app_client):
    user_id = uuid.uuid4()
    response = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["exercise_type"] == "running"
    assert body["duration_minutes"] == 30
    assert uuid.UUID(body["entry_id"])


async def test_post_negative_duration_returns_422(app_client):
    response = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": -5,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 422


async def test_post_unrecognized_exercise_type_returns_422(app_client):
    response = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "rock_climbing",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 422


async def test_post_unauthenticated_returns_401(app_client):
    response = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
    )
    assert response.status_code == 401


async def test_patch_valid_update_returns_200(app_client):
    user_id = uuid.uuid4()
    created = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(user_id),
    )
    entry_id = created.json()["entry_id"]

    response = await app_client.patch(
        f"/api/v1/activity/exercises/{entry_id}",
        json={"duration_minutes": 45},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 200
    assert response.json()["duration_minutes"] == 45


async def test_patch_nonexistent_entry_returns_404(app_client):
    response = await app_client.patch(
        f"/api/v1/activity/exercises/{uuid.uuid4()}",
        json={"duration_minutes": 45},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 404


async def test_patch_another_users_entry_returns_404_never_403(app_client):
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    created = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(owner_id),
    )
    entry_id = created.json()["entry_id"]

    response = await app_client.patch(
        f"/api/v1/activity/exercises/{entry_id}",
        json={"duration_minutes": 45},
        headers=auth_headers(other_user_id),
    )
    assert response.status_code == 404


async def test_patch_invalid_field_value_returns_422(app_client):
    user_id = uuid.uuid4()
    created = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(user_id),
    )
    entry_id = created.json()["entry_id"]

    response = await app_client.patch(
        f"/api/v1/activity/exercises/{entry_id}",
        json={"duration_minutes": -1},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 422


async def test_delete_existing_entry_returns_204(app_client):
    user_id = uuid.uuid4()
    created = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(user_id),
    )
    entry_id = created.json()["entry_id"]

    response = await app_client.delete(
        f"/api/v1/activity/exercises/{entry_id}", headers=auth_headers(user_id)
    )
    assert response.status_code == 204


async def test_delete_nonexistent_entry_returns_404(app_client):
    response = await app_client.delete(
        f"/api/v1/activity/exercises/{uuid.uuid4()}", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 404


async def test_delete_another_users_entry_returns_404_never_403(app_client):
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    created = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(owner_id),
    )
    entry_id = created.json()["entry_id"]

    response = await app_client.delete(
        f"/api/v1/activity/exercises/{entry_id}", headers=auth_headers(other_user_id)
    )
    assert response.status_code == 404


async def test_delete_twice_is_idempotent_204(app_client):
    user_id = uuid.uuid4()
    created = await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(user_id),
    )
    entry_id = created.json()["entry_id"]

    first = await app_client.delete(
        f"/api/v1/activity/exercises/{entry_id}", headers=auth_headers(user_id)
    )
    second = await app_client.delete(
        f"/api/v1/activity/exercises/{entry_id}", headers=auth_headers(user_id)
    )
    assert first.status_code == 204
    assert second.status_code == 204


async def test_get_returns_entries_for_date(app_client):
    user_id = uuid.uuid4()
    await app_client.post(
        "/api/v1/activity/exercises",
        json={
            "exercise_type": "running",
            "duration_minutes": 30,
            "calories_burned_kcal": 250.0,
            "occurred_at": "2026-08-20T07:00:00Z",
        },
        headers=auth_headers(user_id),
    )

    response = await app_client.get(
        "/api/v1/activity/exercises",
        params={"date": "2026-08-20"},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["exercise_type"] == "running"


async def test_get_malformed_date_returns_422(app_client):
    response = await app_client.get(
        "/api/v1/activity/exercises",
        params={"date": "not-a-date"},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 422
