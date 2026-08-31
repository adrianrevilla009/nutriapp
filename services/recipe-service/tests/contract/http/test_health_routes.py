from __future__ import annotations


async def test_liveness_ok(app_client):
    client, _container = app_client
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_ok(app_client):
    client, _container = app_client
    response = await client.get("/health/ready")
    assert response.status_code == 200
