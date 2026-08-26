from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers, project_pending_outbox_events


async def test_start_fasting_window_happy_path(app_client):
    user_id = uuid.uuid4()
    response = await app_client.post(
        "/api/v1/diary/fasting-windows/start", headers=auth_headers(user_id)
    )
    assert response.status_code == 200
    assert "window_id" in response.json()


async def test_start_fasting_window_while_open_returns_409(app_client):
    user_id = uuid.uuid4()
    await app_client.post("/api/v1/diary/fasting-windows/start", headers=auth_headers(user_id))
    response = await app_client.post(
        "/api/v1/diary/fasting-windows/start", headers=auth_headers(user_id)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "FASTING_WINDOW_OVERLAP"


async def test_end_fasting_window_happy_path(app_client):
    user_id = uuid.uuid4()
    started = await app_client.post(
        "/api/v1/diary/fasting-windows/start", headers=auth_headers(user_id)
    )
    window_id = started.json()["window_id"]

    response = await app_client.post(
        f"/api/v1/diary/fasting-windows/{window_id}/end", headers=auth_headers(user_id)
    )
    assert response.status_code == 200


async def test_end_another_users_window_returns_404(app_client):
    owner_id = uuid.uuid4()
    started = await app_client.post(
        "/api/v1/diary/fasting-windows/start", headers=auth_headers(owner_id)
    )
    window_id = started.json()["window_id"]

    response = await app_client.post(
        f"/api/v1/diary/fasting-windows/{window_id}/end", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 404


async def test_get_fasting_history_returns_started_window(app_client, db_engine):
    user_id = uuid.uuid4()
    await app_client.post("/api/v1/diary/fasting-windows/start", headers=auth_headers(user_id))
    await project_pending_outbox_events(db_engine)
    response = await app_client.get("/api/v1/diary/fasting-windows", headers=auth_headers(user_id))
    assert response.status_code == 200
    assert len(response.json()["windows"]) == 1
