"""BillingEntitlementClient -- against a fixture HTTP transport (never a
live billing-service call): entitled/unentitled mapping, and the
`billing_entitlement_check` circuit breaker trips after repeated failures
and recovers after `reset_timeout` (resilience-patterns SKILL.md,
test-plan section 3)."""

from __future__ import annotations

import uuid

import httpx
import pytest

from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from infrastructure.external.billing_entitlement_client import BillingEntitlementClient


def _client(handler, **kwargs) -> BillingEntitlementClient:
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return BillingEntitlementClient(
        base_url="http://billing-service:8000",
        credential="test-credential",
        http_client=http_client,
        **kwargs,
    )


async def test_entitled_true():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"user_id": str(uuid.uuid4()), "entitled": True})

    client = _client(handler)
    assert await client.check_entitlement(uuid.uuid4()) is True
    await client.aclose()


async def test_entitled_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"user_id": str(uuid.uuid4()), "entitled": False})

    client = _client(handler)
    assert await client.check_entitlement(uuid.uuid4()) is False
    await client.aclose()


async def test_credential_rejected_is_unavailable_not_a_crash():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid credential"})

    client = _client(handler)
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(uuid.uuid4())
    await client.aclose()


async def test_circuit_opens_after_fail_max_consecutive_failures():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, json={"error": "boom"})

    client = _client(handler, fail_max=3, reset_timeout_seconds=60)
    user_id = uuid.uuid4()

    for _ in range(3):
        with pytest.raises(EntitlementCheckUnavailableError):
            await client.check_entitlement(user_id)

    calls_before_open = call_count
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(user_id)

    # Once open, no further HTTP calls are attempted -- fails fast.
    assert call_count == calls_before_open
    await client.aclose()


async def test_circuit_recovers_after_reset_timeout():
    import asyncio

    should_fail = True

    def handler(request: httpx.Request) -> httpx.Response:
        if should_fail:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"user_id": str(uuid.uuid4()), "entitled": True})

    client = _client(handler, fail_max=2, reset_timeout_seconds=0.2)
    user_id = uuid.uuid4()

    for _ in range(2):
        with pytest.raises(EntitlementCheckUnavailableError):
            await client.check_entitlement(user_id)

    await asyncio.sleep(0.3)
    should_fail = False

    result = await client.check_entitlement(user_id)
    assert result is True
    await client.aclose()
