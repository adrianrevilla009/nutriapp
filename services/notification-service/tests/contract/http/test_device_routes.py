"""Contract tests for the stubbed POST /api/v1/notifications/devices
(implementation plan section 9.3, test-plan section 3): registration
plumbing only, no downstream send behavior asserted."""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_register_device_accepts_valid_payload(app_client):
    response = await app_client.post(
        "/api/v1/notifications/devices",
        headers=auth_headers(uuid.uuid4()),
        json={"device_token": "abc-token", "platform": "ios"},
    )
    assert response.status_code == 200
    assert response.json() == {"accepted": True}


async def test_register_device_malformed_payload_is_422(app_client):
    response = await app_client.post(
        "/api/v1/notifications/devices",
        headers=auth_headers(uuid.uuid4()),
        json={"device_token": "", "platform": "not-a-platform"},
    )
    assert response.status_code == 422


async def test_register_device_requires_authentication(app_client):
    response = await app_client.post(
        "/api/v1/notifications/devices", json={"device_token": "abc-token", "platform": "ios"}
    )
    assert response.status_code == 401
