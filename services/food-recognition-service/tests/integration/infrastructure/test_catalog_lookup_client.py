"""CatalogLookupClient -- circuit breaker trip/half-open/recover, against a
fixture HTTP double (httpx.MockTransport) standing in for catalog-service's
internal lookup endpoint -- never a real catalog-service instance in this
service's own test suite (test-plan section 2's explicit "never a live
call" requirement).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from domain.ports.catalog_lookup_port import CatalogLookupUnavailableError
from domain.value_objects.barcode import Barcode
from infrastructure.external.catalog_lookup_client import CatalogLookupClient

BARCODE = Barcode("4006381333931")

_SUCCESS_BODY = {
    "product_id": "11111111-1111-1111-1111-111111111111",
    "barcode": "4006381333931",
    "name": "Test Product",
    "brand": "Test Brand",
    "category": "snacks",
    "nutrition_per_100g": {"energy_kcal": 250.0, "protein_g": 5.0},
    "dietary_tags": ["vegan"],
    "allergen_tags": [],
    "package_size": {"value": 100.0, "unit": "g"},
    "price": {"amount": 1.5, "currency": "EUR"},
    "sources": ["open_food_facts"],
}


def _client_with_transport(handler, fail_max: int = 3, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://catalog-service")
    return CatalogLookupClient(
        base_url="http://catalog-service",
        credential="test-credential",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_known_barcode_returns_product_and_sends_credential_header():
    received_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(request.headers)
        assert request.url.params["barcode"] == str(BARCODE)
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler)
    product = await client.lookup_by_barcode(BARCODE)

    assert product is not None
    assert product.name == "Test Product"
    assert product.nutrition_per_100g is not None
    assert product.nutrition_per_100g.energy_kcal == 250.0
    assert received_headers.get("x-internal-service-credential") == "test-credential"
    await client.aclose()


async def test_unknown_barcode_returns_none_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client_with_transport(handler, fail_max=1)
    product = await client.lookup_by_barcode(BARCODE)
    assert product is None

    # A second call still reaches the transport (breaker not tripped by a 404).
    product_again = await client.lookup_by_barcode(BARCODE)
    assert product_again is None
    await client.aclose()


async def test_401_and_403_raise_unavailable():
    for status_code in (401, 403):

        def handler(request: httpx.Request, code=status_code) -> httpx.Response:
            return httpx.Response(code)

        client = _client_with_transport(handler)
        with pytest.raises(CatalogLookupUnavailableError):
            await client.lookup_by_barcode(BARCODE)
        await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_recovers_half_open():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(500)
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    with pytest.raises(CatalogLookupUnavailableError):
        await client.lookup_by_barcode(BARCODE)
    with pytest.raises(CatalogLookupUnavailableError):
        await client.lookup_by_barcode(BARCODE)

    # Circuit now open: the next call fails fast without reaching the
    # transport at all (call_count must not increase).
    calls_before = call_count["n"]
    with pytest.raises(CatalogLookupUnavailableError):
        await client.lookup_by_barcode(BARCODE)
    assert call_count["n"] == calls_before

    # After reset_timeout, a half-open trial call succeeds and closes the circuit.
    await asyncio.sleep(0.3)
    product = await client.lookup_by_barcode(BARCODE)
    assert product is not None
    await client.aclose()


async def test_transport_error_raises_unavailable_after_retries():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    client = _client_with_transport(handler, fail_max=5)
    with pytest.raises(CatalogLookupUnavailableError):
        await client.lookup_by_barcode(BARCODE)
    assert call_count["n"] == 3  # tenacity retry: 3 attempts
    await client.aclose()
