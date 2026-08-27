"""ProfileRevealClient -- circuit breaker trip/half-open/recover, against a
fixture HTTP double (httpx.MockTransport) -- never a real profile-service
instance in this service's own test suite (test-plan section 2, per the
plan's explicit "never a live call" requirement).
"""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

from domain.ports.profile_reveal_port import ProfileRevealUnavailableError
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.sex import Sex
from infrastructure.http.profile_reveal_client import ProfileRevealClient

USER_ID = uuid.uuid4()

_SUCCESS_BODY = {
    "weight_kg": 70.0,
    "height_cm": 175.0,
    "age": 25,
    "sex": "MALE",
    "activity_level": "MODERATE",
    "goal_type": "MAINTAIN",
}


def _client_with_transport(handler, fail_max: int = 3, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://profile-service")
    return ProfileRevealClient(
        base_url="http://profile-service",
        credential="test-credential",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_successful_reveal_returns_metrics_and_sends_credential_header():
    received_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(request.headers)
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler)
    metrics = await client.reveal(USER_ID)

    assert metrics.weight_kg == 70.0
    assert metrics.sex is Sex.MALE
    assert metrics.activity_level is ActivityLevel.MODERATE
    assert metrics.goal_type is GoalType.MAINTAIN
    assert received_headers.get("x-internal-service-credential") == "test-credential"
    await client.aclose()


async def test_404_raises_unavailable_without_tripping_breaker():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client_with_transport(handler, fail_max=1)
    with pytest.raises(ProfileRevealUnavailableError):
        await client.reveal(USER_ID)

    # A second call still reaches the transport (breaker not tripped by a 404).
    with pytest.raises(ProfileRevealUnavailableError):
        await client.reveal(USER_ID)
    await client.aclose()


async def test_401_and_429_raise_unavailable():
    for status_code in (401, 403, 429):

        def handler(request: httpx.Request, code=status_code) -> httpx.Response:
            return httpx.Response(code)

        client = _client_with_transport(handler)
        with pytest.raises(ProfileRevealUnavailableError):
            await client.reveal(USER_ID)
        await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_recovers_half_open():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(500)
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    # Two consecutive 5xx failures trip the breaker (fail_max=2).
    with pytest.raises(ProfileRevealUnavailableError):
        await client.reveal(USER_ID)
    with pytest.raises(ProfileRevealUnavailableError):
        await client.reveal(USER_ID)

    # Circuit now open: the next call fails fast without reaching the
    # transport at all (call_count must not increase).
    calls_before = call_count["n"]
    with pytest.raises(ProfileRevealUnavailableError):
        await client.reveal(USER_ID)
    assert call_count["n"] == calls_before

    # After reset_timeout, a half-open trial call succeeds and closes the circuit.
    await asyncio.sleep(0.3)
    metrics = await client.reveal(USER_ID)
    assert metrics.weight_kg == 70.0
    await client.aclose()


async def test_missing_required_field_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        incomplete = dict(_SUCCESS_BODY)
        del incomplete["goal_type"]
        return httpx.Response(200, json=incomplete)

    client = _client_with_transport(handler)
    with pytest.raises(ProfileRevealUnavailableError):
        await client.reveal(USER_ID)
    await client.aclose()
