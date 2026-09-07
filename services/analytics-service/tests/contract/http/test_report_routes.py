"""GET /api/v1/analytics/reports/{report_type} -- test-plan section 4.
Pro-gated: 200/text-csv for an entitled user, 402/NOT_ENTITLED otherwise."""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_entitled_user_receives_csv(app_client):
    client, container = app_client
    container.entitlement_check.result = True
    user_id = uuid.uuid4()

    response = await client.get(
        "/api/v1/analytics/reports/full",
        params={"start_date": "2026-06-01", "end_date": "2026-06-08"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("#")


async def test_unentitled_user_returns_402(app_client):
    client, container = app_client
    container.entitlement_check.result = False

    response = await client.get(
        "/api/v1/analytics/reports/full",
        params={"start_date": "2026-06-01", "end_date": "2026-06-08"},
        headers=auth_headers(uuid.uuid4()),
    )

    assert response.status_code == 402
    assert response.json()["code"] == "NOT_ENTITLED"


async def test_report_unauthenticated_returns_401(app_client):
    client, _container = app_client
    response = await client.get(
        "/api/v1/analytics/reports/full",
        params={"start_date": "2026-06-01", "end_date": "2026-06-08"},
    )
    assert response.status_code == 401
