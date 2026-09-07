"""BillingEntitlementClient -- against mocked HTTP responses only, same
convention as analytics-service's/recipe-service's own test of this
adapter shape."""

from __future__ import annotations

import uuid

import httpx
import pytest

from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from infrastructure.external.billing_entitlement_client import BillingEntitlementClient


def _client_with_transport(handler, fail_max: int = 5, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return BillingEntitlementClient(
        base_url="http://billing-service:8000",
        credential="test-credential",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_entitled_true() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"entitled": True})

    client = _client_with_transport(handler)
    assert await client.check_entitlement(uuid.uuid4()) is True
    await client.aclose()


async def test_entitled_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"entitled": False})

    client = _client_with_transport(handler)
    assert await client.check_entitlement(uuid.uuid4()) is False
    await client.aclose()


async def test_credential_rejected_raises_unavailable_never_retried_as_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    client = _client_with_transport(handler)
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(uuid.uuid4())
    await client.aclose()


async def test_repeated_5xx_trips_circuit_breaker() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, json={"error": "boom"})

    client = _client_with_transport(handler, fail_max=1, reset_timeout_seconds=5.0)
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(uuid.uuid4())
    calls_before = call_count["n"]

    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(uuid.uuid4())
    assert call_count["n"] == calls_before  # circuit open, no new network attempt
    await client.aclose()


async def test_circuit_recovers_after_reset_timeout() -> None:
    import asyncio

    state = {"fail": True}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["fail"]:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"entitled": True})

    client = _client_with_transport(handler, fail_max=1, reset_timeout_seconds=0.05)
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(uuid.uuid4())

    await asyncio.sleep(0.1)
    state["fail"] = False
    assert await client.check_entitlement(uuid.uuid4()) is True
    await client.aclose()
