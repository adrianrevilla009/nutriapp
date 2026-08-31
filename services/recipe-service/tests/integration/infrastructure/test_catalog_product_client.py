"""CatalogProductClient -- circuit breaker trip/half-open/recover, against
a fixture HTTP double (httpx.MockTransport) standing in for catalog-service's
public product endpoint -- never a real catalog-service instance in this
service's own test suite (test-plan section 2's explicit "never a live
call" requirement)."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import httpx
import pytest

from domain.ports.catalog_product_port import CatalogProductUnavailableError
from infrastructure.external.catalog_product_client import CatalogProductClient

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "catalog_responses"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


PRODUCT_ID = uuid.uuid4()

_SUCCESS_BODY = {
    "product_id": str(PRODUCT_ID),
    "barcode": "4006381333931",
    "name": "Test Product",
    "brand": "Test Brand",
    "category": "snacks",
    "nutrition_per_100g": {
        "energy_kcal": 250.0,
        "protein_g": 5.0,
        "carbohydrates_g": 30.0,
        "fat_g": 8.0,
    },
    "dietary_tags": ["vegan"],
    "allergen_tags": [],
    "package_size": {"value": 100.0, "unit": "g"},
    "price": {"amount": 1.5, "currency": "EUR"},
    "sources": ["open_food_facts"],
}


def _client_with_transport(handler, fail_max: int = 3, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://catalog-service")
    return CatalogProductClient(
        base_url="http://catalog-service",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_known_product_id_returns_resolved_product_with_nutrition():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v1/catalog/products/{PRODUCT_ID}"
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler)
    product = await client.get_product(PRODUCT_ID)

    assert product is not None
    assert product.product_id == PRODUCT_ID
    assert product.nutrition_per_100g is not None
    assert product.nutrition_per_100g.energy_kcal == 250.0
    assert product.nutrition_per_100g.carbohydrates_g == 30.0
    await client.aclose()


async def test_unknown_product_id_returns_none_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client_with_transport(handler, fail_max=1)
    product = await client.get_product(PRODUCT_ID)
    assert product is None

    # A second call still reaches the transport (breaker not tripped by a 404).
    product_again = await client.get_product(PRODUCT_ID)
    assert product_again is None
    await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_recovers_half_open():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(500)
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    with pytest.raises(CatalogProductUnavailableError):
        await client.get_product(PRODUCT_ID)
    with pytest.raises(CatalogProductUnavailableError):
        await client.get_product(PRODUCT_ID)

    # Circuit now open: the next call fails fast without reaching the
    # transport at all (call_count must not increase).
    calls_before = call_count["n"]
    with pytest.raises(CatalogProductUnavailableError):
        await client.get_product(PRODUCT_ID)
    assert call_count["n"] == calls_before

    # After reset_timeout, a half-open trial call succeeds and closes the circuit.
    await asyncio.sleep(0.3)
    product = await client.get_product(PRODUCT_ID)
    assert product is not None
    await client.aclose()


async def test_fixture_response_with_full_nutrition_panel_parses_all_fields():
    body = _load_fixture("resolved_product_full_nutrition.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = _client_with_transport(handler)
    product = await client.get_product(uuid.UUID(body["product_id"]))

    assert product is not None
    assert product.nutrition_per_100g is not None
    assert product.nutrition_per_100g.fiber_g == 10.6
    assert product.nutrition_per_100g.iron_mg == 4.7
    await client.aclose()


async def test_fixture_response_with_missing_nutrition_panel_resolves_to_none_panel():
    body = _load_fixture("resolved_product_missing_nutrition.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = _client_with_transport(handler)
    product = await client.get_product(uuid.UUID(body["product_id"]))

    assert product is not None
    assert product.nutrition_per_100g is None
    await client.aclose()


async def test_transport_error_raises_unavailable_after_retries():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    client = _client_with_transport(handler, fail_max=5)
    with pytest.raises(CatalogProductUnavailableError):
        await client.get_product(PRODUCT_ID)
    assert call_count["n"] == 3  # tenacity retry: 3 attempts
    await client.aclose()
