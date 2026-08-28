"""Liveness/readiness contract."""

from __future__ import annotations

pytestmark_note = "uses app_client fixture from conftest.py"


async def test_liveness(app_client):
    response = await app_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness(app_client):
    response = await app_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
