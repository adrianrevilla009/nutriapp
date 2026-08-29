"""SesEmailAdapter -- circuit breaker trip/half-open/recover, against a
fixture HTTP double standing in for SES sandbox mode -- never a real SES
call (docs/notifications.md section 5, test-plan section 2)."""

from __future__ import annotations

import asyncio

import httpx

from domain.ports.email_provider_port import EmailProviderUnavailableError
from infrastructure.external.ses_email_adapter import CIRCUIT_NAME, SesEmailAdapter


def _client_with_transport(handler, fail_max: int = 3, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://ses-fake")
    return SesEmailAdapter(
        base_url="http://ses-fake",
        from_address="no-reply@nutriapp.example",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


def test_circuit_name_is_independently_named():
    assert CIRCUIT_NAME == "ses_email"
    assert CIRCUIT_NAME not in ("sns_push", "identity_token_reveal")


async def test_well_formed_send_succeeds():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message_id": "ses-msg-1"})

    client = _client_with_transport(handler)
    result = await client.send(
        to="user@example.com", subject="hi", html_body="<p>hi</p>", correlation_id="corr-1"
    )
    assert result.provider_message_id == "ses-msg-1"
    await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_recovers_half_open():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(500)
        return httpx.Response(200, json={"message_id": "ses-msg-2"})

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    for _ in range(2):
        raised = False
        try:
            await client.send(to="a@example.com", subject="s", html_body="b", correlation_id="c")
        except EmailProviderUnavailableError:
            raised = True
        assert raised

    calls_before = call_count["n"]
    raised = False
    try:
        await client.send(to="a@example.com", subject="s", html_body="b", correlation_id="c")
    except EmailProviderUnavailableError:
        raised = True
    assert raised
    assert call_count["n"] == calls_before

    await asyncio.sleep(0.3)
    result = await client.send(to="a@example.com", subject="s", html_body="b", correlation_id="c")
    assert result.provider_message_id == "ses-msg-2"
    await client.aclose()
