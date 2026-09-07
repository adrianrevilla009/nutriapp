from __future__ import annotations


async def test_liveness_and_readiness(app_client):
    client, _container = app_client
    live = await client.get("/health/live")
    ready = await client.get("/health/ready")
    assert live.status_code == 200
    assert ready.status_code == 200
