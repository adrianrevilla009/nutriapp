from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers, project_pending_outbox_events


async def _log_intake(client, user_id, amount_ml: float = 250.0):
    return await client.post(
        "/api/v1/diary/water-intake",
        json=dict(amount_ml=amount_ml, occurred_at="2026-08-26T08:00:00Z"),
        headers=auth_headers(user_id),
    )


async def test_log_water_intake_happy_path(app_client):
    user_id = uuid.uuid4()
    response = await _log_intake(app_client, user_id)
    assert response.status_code == 200
    assert response.json()["amount_ml"] == 250.0


async def test_log_water_intake_non_positive_rejected_by_schema(app_client):
    response = await app_client.post(
        "/api/v1/diary/water-intake",
        json=dict(amount_ml=0, occurred_at="2026-08-26T08:00:00Z"),
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 422


async def test_remove_water_intake_happy_path(app_client):
    user_id = uuid.uuid4()
    logged = await _log_intake(app_client, user_id)
    intake_id = logged.json()["intake_id"]

    response = await app_client.delete(
        f"/api/v1/diary/water-intake/{intake_id}", headers=auth_headers(user_id)
    )
    assert response.status_code == 200
    assert response.json()["removed"] is True


async def test_remove_another_users_intake_returns_403(app_client):
    owner_id = uuid.uuid4()
    logged = await _log_intake(app_client, owner_id)
    intake_id = logged.json()["intake_id"]

    response = await app_client.delete(
        f"/api/v1/diary/water-intake/{intake_id}", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 403


async def test_remove_unknown_intake_returns_404(app_client):
    response = await app_client.delete(
        f"/api/v1/diary/water-intake/{uuid.uuid4()}", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 404


async def test_list_water_intake_returns_logged_entry(app_client, db_engine):
    user_id = uuid.uuid4()
    await _log_intake(app_client, user_id)
    await project_pending_outbox_events(db_engine)
    response = await app_client.get("/api/v1/diary/water-intake", headers=auth_headers(user_id))
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 1
