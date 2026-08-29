"""NutritionCalculationServiceClient -- circuit breaker trip/half-open/
recover, run independently for `get_totals` and `get_target` (test-plan
section 2: the two breakers must be independently named and tripping one
must not affect the other), against a fixture HTTP double
(httpx.MockTransport) -- never a real nutrition-calculation-service
instance in this service's own test suite."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest

from domain.ports.nutrition_target_port import (
    NutritionTargetNotComputedYet,
    NutritionTargetUnavailableError,
)
from domain.ports.nutrition_totals_port import NutritionTotalsUnavailableError
from infrastructure.external.nutrition_calculation_service_client import (
    NutritionCalculationServiceClient,
)
from tests.fixtures.downstream_fixtures import load_downstream_fixture

TOTAL_DATE = date(2026, 8, 28)
AUTH_HEADER = "Bearer test-token"

_TOTALS_SUCCESS_BODY = load_downstream_fixture("nutrition_totals_success")
_TARGET_SUCCESS_BODY = load_downstream_fixture("nutrition_target_success")
_TARGET_NOT_YET_COMPUTED_BODY = load_downstream_fixture("target_not_yet_computed")


def _client_with_transport(handler, fail_max: int = 3, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(
        transport=transport, base_url="http://nutrition-calculation-service"
    )
    return NutritionCalculationServiceClient(
        base_url="http://nutrition-calculation-service",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


# --- get_totals -------------------------------------------------------


async def test_totals_successful_call_maps_response_and_forwards_authorization_header():
    received_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(request.headers)
        assert request.url.path == "/api/v1/nutrition/totals/2026-08-28"
        return httpx.Response(200, json=_TOTALS_SUCCESS_BODY)

    client = _client_with_transport(handler)
    result = await client.get_totals(TOTAL_DATE, AUTH_HEADER)

    assert result.calories_kcal == 1820.0
    assert result.micronutrients == {"vitamin_c_mg": 90.0}
    assert received_headers.get("authorization") == AUTH_HEADER
    await client.aclose()


async def test_totals_5xx_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = _client_with_transport(handler)
    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    await client.aclose()


async def test_totals_circuit_trips_then_fails_fast_then_recovers():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(503)
        return httpx.Response(200, json=_TOTALS_SUCCESS_BODY)

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)

    calls_before = call_count["n"]
    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    assert call_count["n"] == calls_before

    await asyncio.sleep(0.3)
    result = await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    assert result.calories_kcal == 1820.0
    await client.aclose()


async def test_totals_malformed_response_body_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"calories_kcal": 1820.0})  # missing fields

    client = _client_with_transport(handler)
    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    await client.aclose()


async def test_totals_401_does_not_trip_breaker_but_is_surfaced_as_unavailable():
    """test-plan Addendum -- 2026-08-29: a 401 reflects a problem with
    THIS caller's forwarded token, not nutrition-calculation-service's
    health, so it must not count toward the "nutrition_totals" breaker's
    failure threshold."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(401)

    client = _client_with_transport(handler, fail_max=1)

    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    assert call_count["n"] == 1

    # A second call still reaches the transport -- fail_max=1 would have
    # tripped the breaker already if the 401 had counted as a failure.
    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    assert call_count["n"] == 2
    await client.aclose()


async def test_totals_timeout_counts_toward_breaker_and_trips_it_after_threshold():
    """test-plan Addendum -- 2026-08-29: unlike a 401, a transport-level
    timeout IS a genuine service-health signal and must count toward the
    breaker."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    client = _client_with_transport(handler, fail_max=1, reset_timeout_seconds=60.0)

    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)

    # tenacity retries a transport error internally (up to 3 attempts)
    # before giving up -- that whole sequence counts as ONE failure
    # against the breaker (fail_max=1), so it is now open.
    calls_after_trip = call_count["n"]
    assert calls_after_trip >= 1

    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    assert call_count["n"] == calls_after_trip
    await client.aclose()


# --- get_target ---------------------------------------------------------


async def test_target_successful_call_maps_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/nutrition/target"
        return httpx.Response(200, json=_TARGET_SUCCESS_BODY)

    client = _client_with_transport(handler)
    result = await client.get_target(AUTH_HEADER)

    assert result.calorie_target_kcal == 2200.0
    assert result.goal_type == "MAINTAIN"
    await client.aclose()


async def test_target_404_maps_to_not_computed_yet_not_an_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json=_TARGET_NOT_YET_COMPUTED_BODY)

    client = _client_with_transport(handler, fail_max=1)
    result = await client.get_target(AUTH_HEADER)

    assert isinstance(result, NutritionTargetNotComputedYet)
    # A second call still reaches the transport (breaker not tripped by a 404).
    result_again = await client.get_target(AUTH_HEADER)
    assert isinstance(result_again, NutritionTargetNotComputedYet)
    await client.aclose()


async def test_target_5xx_raises_unavailable_distinct_from_404_case():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = _client_with_transport(handler)
    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)
    await client.aclose()


async def test_target_circuit_trips_then_fails_fast_then_recovers():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(503)
        return httpx.Response(200, json=_TARGET_SUCCESS_BODY)

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)
    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)

    calls_before = call_count["n"]
    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)
    assert call_count["n"] == calls_before

    await asyncio.sleep(0.3)
    result = await client.get_target(AUTH_HEADER)
    assert result.calorie_target_kcal == 2200.0
    await client.aclose()


async def test_target_malformed_response_body_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"calorie_target_kcal": 2200.0})  # missing fields

    client = _client_with_transport(handler)
    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)
    await client.aclose()


async def test_target_401_does_not_trip_breaker_but_is_surfaced_as_unavailable():
    """test-plan Addendum -- 2026-08-29: a 401 reflects a problem with
    THIS caller's forwarded token, not nutrition-calculation-service's
    health, so it must not count toward the "nutrition_target" breaker's
    failure threshold -- distinct from the 404 "not yet computed" case,
    which is also excluded but for the different reason that it's a
    well-formed business response, not an auth failure."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(401)

    client = _client_with_transport(handler, fail_max=1)

    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)
    assert call_count["n"] == 1

    # A second call still reaches the transport -- fail_max=1 would have
    # tripped the breaker already if the 401 had counted as a failure.
    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)
    assert call_count["n"] == 2
    await client.aclose()


async def test_target_timeout_counts_toward_breaker_and_trips_it_after_threshold():
    """test-plan Addendum -- 2026-08-29: unlike a 401, a transport-level
    timeout IS a genuine service-health signal and must count toward the
    breaker."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    client = _client_with_transport(handler, fail_max=1, reset_timeout_seconds=60.0)

    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)

    calls_after_trip = call_count["n"]
    assert calls_after_trip >= 1

    with pytest.raises(NutritionTargetUnavailableError):
        await client.get_target(AUTH_HEADER)
    assert call_count["n"] == calls_after_trip
    await client.aclose()


# --- independence between the two named breakers ------------------------


async def test_totals_breaker_open_does_not_affect_target_breaker_health():
    totals_call_count = {"n": 0}
    target_call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/totals/" in request.url.path:
            totals_call_count["n"] += 1
            return httpx.Response(503)
        target_call_count["n"] += 1
        return httpx.Response(200, json=_TARGET_SUCCESS_BODY)

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=60.0)

    # Trip the totals breaker.
    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)

    # Confirm the totals breaker is now open (fails fast, no new transport call).
    calls_before = totals_call_count["n"]
    with pytest.raises(NutritionTotalsUnavailableError):
        await client.get_totals(TOTAL_DATE, AUTH_HEADER)
    assert totals_call_count["n"] == calls_before

    # get_target must still reach the transport -- its breaker is
    # independent and untouched by the totals breaker being open.
    result = await client.get_target(AUTH_HEADER)
    assert result.calorie_target_kcal == 2200.0
    assert target_call_count["n"] == 1
    await client.aclose()
