"""VCR-style fixture-based tests for UsdaFdcSourceAdapter — never a live
request. Fixture response bodies (`tests/fixtures/cassettes/usda_fdc/`)
are hand-authored, shaped exactly like the documented USDA FDC Branded
Foods API response schema, and served via `httpx.MockTransport` so no
real network call is ever attempted (external-data-ethics SKILL.md /
test-plan section 2)."""

from __future__ import annotations

import json
import os

import httpx
import pytest
from redis.asyncio import Redis

from infrastructure.external.usda_fdc.circuit_breaker import UsdaFdcCircuitBreaker
from infrastructure.external.usda_fdc.usda_fdc_client import UsdaFdcClient
from infrastructure.external.usda_fdc.usda_fdc_source_adapter import UsdaFdcSourceAdapter

CASSETTE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "fixtures", "cassettes", "usda_fdc"
)


def _load(name: str) -> dict:
    with open(os.path.join(CASSETTE_DIR, name)) as f:
        return json.load(f)


@pytest.fixture
async def redis_client(redis_url):
    client = Redis.from_url(redis_url)
    yield client
    await client.flushall()
    await client.aclose()


def _success_transport() -> httpx.MockTransport:
    page_1 = _load("branded_foods_page_1.json")
    page_2 = _load("branded_foods_page_2.json")

    def handler(request: httpx.Request) -> httpx.Response:
        page_number = int(request.url.params.get("pageNumber", "1"))
        body = page_1 if page_number == 1 else page_2
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def _rate_limited_transport() -> httpx.MockTransport:
    body = _load("rate_limited_429.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json=body, headers={"Retry-After": "5"})

    return httpx.MockTransport(handler)


async def test_successful_paginated_response_yields_records_and_next_cursor(redis_client):
    http_client = httpx.AsyncClient(transport=_success_transport())
    client = UsdaFdcClient(redis=redis_client, api_key="TEST_KEY", http_client=http_client)
    breaker = UsdaFdcCircuitBreaker(fail_max=5, reset_timeout_seconds=60)
    adapter = UsdaFdcSourceAdapter(client, breaker)

    batch = await adapter.fetch_batch(None)

    assert len(batch.records) == 2
    assert batch.next_cursor == "2"
    names = {r.name for r in batch.records}
    assert "Chocolate Chip Cookies" in names


async def test_pages_to_completion_across_cursor(redis_client):
    http_client = httpx.AsyncClient(transport=_success_transport())
    client = UsdaFdcClient(redis=redis_client, api_key="TEST_KEY", http_client=http_client)
    breaker = UsdaFdcCircuitBreaker(fail_max=5, reset_timeout_seconds=60)
    adapter = UsdaFdcSourceAdapter(client, breaker)

    first = await adapter.fetch_batch(None)
    second = await adapter.fetch_batch(first.next_cursor)

    assert len(second.records) == 1
    assert second.next_cursor is None


async def test_429_response_backs_off_without_hard_failure(redis_client):
    http_client = httpx.AsyncClient(transport=_rate_limited_transport())
    client = UsdaFdcClient(redis=redis_client, api_key="TEST_KEY", http_client=http_client)
    breaker = UsdaFdcCircuitBreaker(fail_max=5, reset_timeout_seconds=60)
    adapter = UsdaFdcSourceAdapter(client, breaker)

    batch = await adapter.fetch_batch(None)

    assert batch.records == ()
    assert batch.next_cursor is None
    assert batch.skipped_count == 1
