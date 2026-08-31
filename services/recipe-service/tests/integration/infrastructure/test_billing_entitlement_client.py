"""BillingEntitlementClient -- circuit breaker trip/half-open/recover,
against a fixture HTTP double standing in for billing-service's internal
entitlement endpoint -- never a real billing-service instance in this
service's own test suite. Also verifies `billing_entitlement_check` never
shares breaker state with `catalog_product_lookup` (implementation plan
section 7)."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import httpx
import pytest

from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from infrastructure.external.billing_entitlement_client import BillingEntitlementClient
from infrastructure.external.catalog_product_client import CatalogProductClient

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


async def test_billing_breaker_never_shares_state_with_catalog_breaker():
    """A tripped `billing_entitlement_check` circuit must not affect
    `catalog_product_lookup` -- independently-named breakers, call-count
    assertion with one breaker open and the other still reaching its own
    fixture server (test-plan section 2)."""

    def always_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    billing_client = _client_with_transport(always_500, fail_max=1, reset_timeout_seconds=60.0)

    with pytest.raises(EntitlementCheckUnavailableError):
        await billing_client.check_entitlement(USER_ID)
    # Breaker now open -- the next call fails fast without reaching the transport.
    with pytest.raises(EntitlementCheckUnavailableError):
        await billing_client.check_entitlement(USER_ID)

    product_id = uuid.uuid4()
    catalog_calls = {"n": 0}

    def catalog_handler(request: httpx.Request) -> httpx.Response:
        catalog_calls["n"] += 1
        return httpx.Response(
            200,
            json={
                "product_id": str(product_id),
                "barcode": None,
                "name": "Independent Product",
                "brand": None,
                "category": None,
                "nutrition_per_100g": None,
                "dietary_tags": [],
                "allergen_tags": [],
                "package_size": None,
                "price": None,
                "sources": [],
            },
        )

    catalog_transport = httpx.MockTransport(catalog_handler)
    catalog_http = httpx.AsyncClient(transport=catalog_transport, base_url="http://catalog-service")
    catalog_client = CatalogProductClient(
        base_url="http://catalog-service", http_client=catalog_http
    )

    product = await catalog_client.get_product(product_id)

    assert product is not None
    assert catalog_calls["n"] == 1  # catalog breaker unaffected by billing breaker's open state

    await billing_client.aclose()
    await catalog_client.aclose()
