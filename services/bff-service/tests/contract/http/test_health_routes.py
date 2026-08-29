"""GET /health/live, /health/ready -- kept dependency-free."""

from __future__ import annotations


async def test_liveness_ok(app_client):
    response = await app_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_ok(app_client):
    response = await app_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
