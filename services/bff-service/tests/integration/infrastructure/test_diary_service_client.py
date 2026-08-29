"""DiaryServiceClient -- circuit breaker trip/half-open/recover, against a
fixture HTTP double (httpx.MockTransport) -- never a real diary-service
instance in this service's own test suite (test-plan section 2)."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest

from domain.ports.diary_summary_port import DiarySummaryUnavailableError
from infrastructure.external.diary_service_client import DiaryServiceClient
from tests.fixtures.downstream_fixtures import load_downstream_fixture

SUMMARY_DATE = date(2026, 8, 28)
AUTH_HEADER = "Bearer test-token"

_SUCCESS_BODY = load_downstream_fixture("diary_summary_success")


def _client_with_transport(handler, fail_max: int = 3, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://diary-service")
    return DiaryServiceClient(
        base_url="http://diary-service",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_successful_call_maps_response_and_forwards_authorization_header():
    received_headers = {}
    received_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(request.headers)
        received_params.update(dict(request.url.params))
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler)
    result = await client.get_summary(SUMMARY_DATE, AUTH_HEADER)

    assert result.total_calories_kcal == 1850.0
    assert result.total_water_ml == 1500.0
    assert result.fasting_windows_ended == 1
    assert received_headers.get("authorization") == AUTH_HEADER
    assert received_params.get("date") == "2026-08-28"
    await client.aclose()


async def test_5xx_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = _client_with_transport(handler)
    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)
    await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_fails_fast_then_recovers():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(503)
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)
    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)

    # Circuit now open: fails fast without reaching the transport.
    calls_before = call_count["n"]
    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)
    assert call_count["n"] == calls_before

    # After reset_timeout, a half-open trial call succeeds and closes the circuit.
    await asyncio.sleep(0.3)
    result = await client.get_summary(SUMMARY_DATE, AUTH_HEADER)
    assert result.total_calories_kcal == 1850.0
    await client.aclose()


async def test_malformed_response_body_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total_calories_kcal": 1850.0})  # missing fields

    client = _client_with_transport(handler)
    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)
    await client.aclose()


async def test_401_does_not_trip_breaker_but_is_surfaced_as_unavailable():
    """test-plan Addendum -- 2026-08-29: a 401 reflects a problem with
    THIS caller's forwarded token, not diary-service's health, so it must
    not count toward the breaker's failure threshold -- a subsequent call
    (even fail_max=1) still reaches the transport."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(401)

    client = _client_with_transport(handler, fail_max=1)

    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)
    calls_after_first = call_count["n"]
    assert calls_after_first == 1

    # A second call still reaches the transport -- fail_max=1 would have
    # tripped the breaker already if the 401 had counted as a failure.
    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)
    assert call_count["n"] == 2
    await client.aclose()


async def test_timeout_counts_toward_breaker_and_trips_it_after_threshold():
    """test-plan Addendum -- 2026-08-29: unlike a 401, a transport-level
    timeout IS a genuine service-health signal and must count toward the
    breaker (this was always the intended design, just previously
    untested)."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    client = _client_with_transport(handler, fail_max=1, reset_timeout_seconds=60.0)

    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)

    # tenacity retries a transport error internally (up to 3 attempts)
    # before giving up -- that whole sequence counts as ONE failure
    # against the breaker (fail_max=1), so it is now open.
    calls_after_trip = call_count["n"]
    assert calls_after_trip >= 1

    # Circuit now open: the next call fails fast via OpenedState, never
    # reaching the transport again (call_count must not increase).
    with pytest.raises(DiarySummaryUnavailableError):
        await client.get_summary(SUMMARY_DATE, AUTH_HEADER)
    assert call_count["n"] == calls_after_trip
    await client.aclose()
