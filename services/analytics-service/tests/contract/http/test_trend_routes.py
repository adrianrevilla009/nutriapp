"""GET /api/v1/analytics/trends/weekly -- test-plan section 4. NOT
Pro-gated: succeeds even when the fake entitlement port would reject."""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_weekly_trend_returns_sample_size_and_window_days(app_client):
    client, container = app_client
    container.entitlement_check.result = False  # deliberately unentitled
    user_id = uuid.uuid4()

    response = await client.get("/api/v1/analytics/trends/weekly", headers=auth_headers(user_id))

    assert response.status_code == 200
    body = response.json()
    assert "sample_size" in body["streak"]
    assert "window_days" in body["streak"]
    assert body["streak"]["sample_size"] == 0
    assert body["running_total"]["sample_size"] == 0
    assert body["running_total"]["avg_calories_kcal"] is None
    assert container.entitlement_check.calls == []  # never consulted -- not gated


async def test_weekly_trend_unauthenticated_returns_401(app_client):
    client, _container = app_client
    response = await client.get("/api/v1/analytics/trends/weekly")
    assert response.status_code == 401
