"""BillingEntitlementClient -- circuit breaker trip/half-open/recover,
against a fixture HTTP double standing in for billing-service's internal
entitlement endpoint -- never a real billing-service instance in this
service's own test suite (test-plan section 2/8)."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import httpx
import pytest

from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from infrastructure.external.billing_entitlement_client import BillingEntitlementClient

USER_ID = uuid.uuid4()
FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "billing_responses"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _client_with_transport(
    handler,
    fail_max: int = 3,
    reset_timeout_seconds: float = 0.2,
    credential: str = "test-credential",
):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://billing-service")
    return BillingEntitlementClient(
        base_url="http://billing-service",
        credential=credential,
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_entitled_user_returns_true_and_sends_credential_header():
    received_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(request.headers)
        assert request.url.path == f"/internal/v1/billing/entitlements/{USER_ID}"
        return httpx.Response(200, json={"user_id": str(USER_ID), "entitled": True})

    client = _client_with_transport(handler)
    result = await client.check_entitlement(USER_ID)

    assert result is True
    assert received_headers.get("x-internal-service-credential") == "test-credential"
    await client.aclose()


async def test_unentitled_user_returns_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"user_id": str(USER_ID), "entitled": False})

    client = _client_with_transport(handler)
    result = await client.check_entitlement(USER_ID)
    assert result is False
    await client.aclose()


async def test_fixture_entitled_true_response():
    body = _load_fixture("entitled_true.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = _client_with_transport(handler)
    assert await client.check_entitlement(USER_ID) is True
    await client.aclose()


async def test_fixture_entitled_false_response():
    body = _load_fixture("entitled_false.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = _client_with_transport(handler)
    assert await client.check_entitlement(USER_ID) is False
    await client.aclose()


async def test_invalid_credential_raises_unavailable():
    for status_code in (401, 403):

        def handler(request: httpx.Request, code=status_code) -> httpx.Response:
            return httpx.Response(code)

        client = _client_with_transport(handler)
        with pytest.raises(EntitlementCheckUnavailableError):
            await client.check_entitlement(USER_ID)
        await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_recovers_half_open():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(500)
        return httpx.Response(200, json={"user_id": str(USER_ID), "entitled": True})

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(USER_ID)
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(USER_ID)

    calls_before = call_count["n"]
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(USER_ID)
    assert call_count["n"] == calls_before

    await asyncio.sleep(0.3)
    result = await client.check_entitlement(USER_ID)
    assert result is True
    await client.aclose()
