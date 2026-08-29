"""SnsPushAdapter -- circuit breaker trip/half-open/recover, against a
local fake push endpoint -- never a real device (docs/notifications.md
section 5, test-plan section 2)."""

from __future__ import annotations

import asyncio

import httpx

from domain.ports.push_provider_port import PushProviderUnavailableError
from infrastructure.external.sns_push_adapter import CIRCUIT_NAME, SnsPushAdapter


def _client_with_transport(handler, fail_max: int = 3, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://sns-fake")
    return SnsPushAdapter(
        base_url="http://sns-fake",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


def test_circuit_name_is_independently_named():
    assert CIRCUIT_NAME == "sns_push"
    assert CIRCUIT_NAME not in ("ses_email", "identity_token_reveal")


async def test_well_formed_send_succeeds():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message_id": "sns-msg-1"})

    client = _client_with_transport(handler)
    result = await client.send(
        device_token="device-1", title="t", body="b", data={"k": "v"}, correlation_id="corr-1"
    )
    assert result.provider_message_id == "sns-msg-1"
    await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_recovers_half_open():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(500)
        return httpx.Response(200, json={"message_id": "sns-msg-2"})

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    for _ in range(2):
        raised = False
        try:
            await client.send(device_token="d", title="t", body="b", data={}, correlation_id="c")
        except PushProviderUnavailableError:
            raised = True
        assert raised

    calls_before = call_count["n"]
    raised = False
    try:
        await client.send(device_token="d", title="t", body="b", data={}, correlation_id="c")
    except PushProviderUnavailableError:
        raised = True
    assert raised
    assert call_count["n"] == calls_before

    await asyncio.sleep(0.3)
    result = await client.send(device_token="d", title="t", body="b", data={}, correlation_id="c")
    assert result.provider_message_id == "sns-msg-2"
    await client.aclose()
