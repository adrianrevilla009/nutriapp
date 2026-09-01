"""BillingEntitlementClient -- circuit breaker trip/half-open/recover,
against a fixture HTTP double standing in for billing-service's internal
entitlement endpoint -- never a real billing-service instance in this
service's own test suite (test-plan section 2/8)."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import httpx
import pytest

from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from infrastructure.external.billing_entitlement_client import BillingEntitlementClient

USER_ID = uuid.uuid4()
FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "billing_responses"

_DEFAULT_TEST_FAIL_MAX = 3
_DEFAULT_TEST_RESET_TIMEOUT_SECONDS = 0.2
_DEFAULT_TEST_CREDENTIAL = "test-credential"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _client_with_transport(
    handler,
    *,
    fail_max: int = _DEFAULT_TEST_FAIL_MAX,
    reset_timeout_seconds: float = _DEFAULT_TEST_RESET_TIMEOUT_SECONDS,
    credential: str = _DEFAULT_TEST_CREDENTIAL,
) -> BillingEntitlementClient:
    return BillingEntitlementClient(
        base_url="http://billing-service",
        credential=credential,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://billing-service"
        ),
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_entitled_user_sends_credential_header():
    received_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(request.headers)
        assert request.url.path == f"/internal/v1/billing/entitlements/{USER_ID}"
        return httpx.Response(200, json={"user_id": str(USER_ID), "entitled": True})

    client = _client_with_transport(handler)
    await client.check_entitlement(USER_ID)

    assert received_headers.get("x-internal-service-credential") == "test-credential"
    await client.aclose()


@pytest.mark.parametrize(
    "response_body,expected_entitled",
    [
        pytest.param({"user_id": str(USER_ID), "entitled": True}, True, id="inline-entitled"),
        pytest.param({"user_id": str(USER_ID), "entitled": False}, False, id="inline-unentitled"),
        pytest.param(_load_fixture("entitled_true.json"), True, id="fixture-entitled"),
        pytest.param(_load_fixture("entitled_false.json"), False, id="fixture-unentitled"),
    ],
)
async def test_check_entitlement_reflects_billing_service_response(
    response_body: dict, expected_entitled: bool
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_body)

    client = _client_with_transport(handler)
    result = await client.check_entitlement(USER_ID)

    assert result is expected_entitled
    await client.aclose()


@pytest.mark.parametrize("rejection_status_code", [401, 403])
async def test_invalid_credential_raises_unavailable(rejection_status_code: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(rejection_status_code)

    client = _client_with_transport(handler)
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(USER_ID)
    await client.aclose()


async def test_circuit_trips_after_consecutive_5xx_then_recovers_half_open():
    responses_sent = {"n": 0}
    failures_before_recovery = 2

    def handler(request: httpx.Request) -> httpx.Response:
        responses_sent["n"] += 1
        if responses_sent["n"] <= failures_before_recovery:
            return httpx.Response(500)
        return httpx.Response(200, json={"user_id": str(USER_ID), "entitled": True})

    client = _client_with_transport(
        handler, fail_max=failures_before_recovery, reset_timeout_seconds=0.2
    )

    for _ in range(failures_before_recovery):
        with pytest.raises(EntitlementCheckUnavailableError):
            await client.check_entitlement(USER_ID)

    calls_while_breaker_open = responses_sent["n"]
    with pytest.raises(EntitlementCheckUnavailableError):
        await client.check_entitlement(USER_ID)
    assert responses_sent["n"] == calls_while_breaker_open  # fails fast, no transport call

    await asyncio.sleep(0.3)
    assert await client.check_entitlement(USER_ID) is True
    await client.aclose()
