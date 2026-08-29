"""IdentityTokenRevealClient -- circuit breaker trip/half-open/recover,
against a fixture HTTP double (httpx.MockTransport) standing in for
identity-service's internal reveal endpoint -- never a real
identity-service instance (test-plan section 2's "never a live call"
requirement). The circuit is independently named (test-plan section 2's
"never shares state with the SES/SNS breakers" structural assertion)."""

from __future__ import annotations

import asyncio
import uuid

import httpx

from domain.ports.token_reveal_port import TokenRevealNotFoundError, TokenRevealUnavailableError
from infrastructure.external.identity_token_reveal_client import (
    CIRCUIT_NAME,
    IdentityTokenRevealClient,
)

REFERENCE_ID = str(uuid.uuid4())
_SUCCESS_BODY = {
    "secret": "raw-secret-value",
    "user_id": str(uuid.uuid4()),
    "kind": "email_verification",
}


def _client_with_transport(handler, fail_max: int = 3, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://identity-service")
    return IdentityTokenRevealClient(
        base_url="http://identity-service",
        credential="test-credential",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


def test_circuit_name_is_independently_named():
    assert CIRCUIT_NAME == "identity_token_reveal"
    assert CIRCUIT_NAME not in ("ses_email", "sns_push")


async def test_valid_reference_id_returns_secret_and_sends_credential_header():
    received_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(request.headers)
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler)
    revealed = await client.reveal(REFERENCE_ID)

    assert revealed.secret == "raw-secret-value"
    assert received_headers.get("x-internal-service-credential") == "test-credential"
    await client.aclose()


async def test_unknown_reference_id_raises_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client_with_transport(handler, fail_max=1)
    try:
        raised = False
        try:
            await client.reveal(REFERENCE_ID)
        except TokenRevealNotFoundError:
            raised = True
        assert raised
    finally:
        await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_recovers_half_open():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(500)
        return httpx.Response(200, json=_SUCCESS_BODY)

    client = _client_with_transport(handler, fail_max=2, reset_timeout_seconds=0.2)

    for _ in range(2):
        raised = False
        try:
            await client.reveal(REFERENCE_ID)
        except TokenRevealUnavailableError:
            raised = True
        assert raised

    calls_before = call_count["n"]
    raised = False
    try:
        await client.reveal(REFERENCE_ID)
    except TokenRevealUnavailableError:
        raised = True
    assert raised
    assert call_count["n"] == calls_before  # fast-failed, transport not reached

    await asyncio.sleep(0.3)
    revealed = await client.reveal(REFERENCE_ID)
    assert revealed.secret == "raw-secret-value"
    await client.aclose()
