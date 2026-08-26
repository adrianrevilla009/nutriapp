from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_get_daily_summary_with_no_data_returns_zeroed_summary(app_client):
    user_id = uuid.uuid4()
    response = await app_client.get(
        "/api/v1/diary/summary", params={"date": "2026-08-26"}, headers=auth_headers(user_id)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_calories_kcal"] == 0.0
    assert body["fasting_windows_ended"] == 0


async def test_missing_authenticated_user_returns_401(app_client):
    response = await app_client.get("/api/v1/diary/summary", params={"date": "2026-08-26"})
    assert response.status_code == 401
