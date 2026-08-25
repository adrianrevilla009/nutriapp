"""Contract tests: happy path + error path per endpoint, against the real
FastAPI/OpenAPI-generated routes and a real (testcontainers) Postgres.
"""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def grant_consent(client, user_id):
    return await client.post("/api/v1/profile/consent", headers=auth_headers(user_id))


async def test_consent_grant_happy_path_returns_true(app_client, seeded_user):
    response = await grant_consent(app_client, seeded_user)
    assert response.status_code == 200
    assert response.json()["consent_granted"] is True


async def test_consent_grant_unknown_user_returns_404(app_client):
    response = await grant_consent(app_client, uuid.uuid4())
    assert response.status_code == 404
    assert sorted(response.json().keys()) == ["code", "error"]


async def test_record_weight_without_consent_returns_403(app_client, seeded_user):
    response = await app_client.post(
        "/api/v1/profile/metrics/weight",
        json=dict(weight_kg=70.0),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CONSENT_REQUIRED"


async def test_record_weight_happy_path_after_consent(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    response = await app_client.post(
        "/api/v1/profile/metrics/weight",
        json=dict(weight_kg=70.0),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 200
    assert response.json()["weight_kg"] == 70.0


async def test_record_weight_non_positive_value_rejected_by_schema(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    response = await app_client.post(
        "/api/v1/profile/metrics/weight",
        json=dict(weight_kg=-5.0),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 422


async def test_record_body_metric_without_consent_returns_403(app_client, seeded_user):
    response = await app_client.post(
        "/api/v1/profile/metrics/body",
        json=dict(metric_type="height", value=175.0),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 403


async def test_record_body_metric_happy_path_after_consent(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    response = await app_client.post(
        "/api/v1/profile/metrics/body",
        json=dict(metric_type="height", value=175.0),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 200
    assert response.json()["metric_type"] == "height"


async def test_set_goal_happy_path(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    response = await app_client.post(
        "/api/v1/profile/goal",
        json=dict(goal_type="MAINTAIN"),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 200
    assert response.json()["goal_type"] == "MAINTAIN"


async def test_set_goal_twice_returns_409(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    await app_client.post(
        "/api/v1/profile/goal", json=dict(goal_type="MAINTAIN"), headers=auth_headers(seeded_user)
    )
    response = await app_client.post(
        "/api/v1/profile/goal", json=dict(goal_type="MAINTAIN"), headers=auth_headers(seeded_user)
    )
    assert response.status_code == 409


async def test_update_goal_without_existing_goal_returns_409(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    response = await app_client.put(
        "/api/v1/profile/goal", json=dict(goal_type="MAINTAIN"), headers=auth_headers(seeded_user)
    )
    assert response.status_code == 409


async def test_update_goal_happy_path(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    await app_client.post(
        "/api/v1/profile/goal", json=dict(goal_type="MAINTAIN"), headers=auth_headers(seeded_user)
    )
    response = await app_client.put(
        "/api/v1/profile/goal",
        json=dict(goal_type="LOSE", target_value=1.0, target_date="2099-01-01"),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 200
    assert response.json()["previous_goal_type"] == "MAINTAIN"


async def test_get_profile_unknown_user_returns_404_not_500_or_empty_200(app_client):
    response = await app_client.get("/api/v1/profile", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 404


async def test_get_profile_happy_path_returns_current_snapshot(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    await app_client.post(
        "/api/v1/profile/metrics/weight",
        json=dict(weight_kg=70.0),
        headers=auth_headers(seeded_user),
    )
    response = await app_client.get("/api/v1/profile", headers=auth_headers(seeded_user))
    assert response.status_code == 200
    body = response.json()
    assert body["weight_kg"] == 70.0
    assert body["consent_granted"] is True


async def test_get_evolution_happy_path_returns_entries(app_client, seeded_user):
    await grant_consent(app_client, seeded_user)
    await app_client.post(
        "/api/v1/profile/metrics/weight",
        json=dict(weight_kg=70.0),
        headers=auth_headers(seeded_user),
    )
    response = await app_client.get(
        "/api/v1/profile/evolution",
        params=dict(metric="weight_kg"),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["value"] == 70.0


async def test_get_evolution_empty_range_returns_empty_list(app_client, seeded_user):
    response = await app_client.get(
        "/api/v1/profile/evolution",
        params=dict(metric="weight_kg"),
        headers=auth_headers(seeded_user),
    )
    assert response.status_code == 200
    assert response.json()["entries"] == []


async def test_missing_authenticated_user_returns_401(app_client):
    response = await app_client.get("/api/v1/profile")
    assert response.status_code == 401
