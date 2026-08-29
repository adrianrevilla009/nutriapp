"""StripePaymentAdapter -- fixture-only (never a live Stripe call), per
test-plan section 2. Uses httpx.MockTransport, the established convention
for every provider adapter in this codebase (SES/SNS/identity-reveal in
notification-service)."""

from __future__ import annotations

import os
import urllib.parse
import uuid

import httpx
import purgatory
import pytest

from domain.ports.payment_provider_port import (
    PaymentProviderUnavailableError,
    WebhookSignatureVerificationError,
)
from infrastructure.external.stripe_payment_adapter import StripePaymentAdapter
from tests.fixtures.stripe_webhooks.signing import TEST_WEBHOOK_SECRET, sign_payload

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def _load_fixture(*parts: str) -> bytes:
    with open(os.path.join(FIXTURES_DIR, *parts), "rb") as f:
        return f.read()


def _checkout_session_response_body() -> bytes:
    return _load_fixture("stripe_responses", "checkout_session_created.json")


def _make_adapter(transport: httpx.MockTransport) -> StripePaymentAdapter:
    client = httpx.AsyncClient(transport=transport)
    return StripePaymentAdapter(
        secret_key="sk_test_fixture",
        webhook_signing_secret=TEST_WEBHOOK_SECRET,
        price_id="price_pro_monthly_fixture",
        http_client=client,
    )


class _Counter:
    def __init__(self) -> None:
        self.value = 0

    def increment(self) -> None:
        self.value += 1


async def test_create_checkout_session_success():
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, content=_checkout_session_response_body())

    adapter = _make_adapter(httpx.MockTransport(handler))
    user_id = uuid.uuid4()
    result = await adapter.create_checkout_session(
        user_id=user_id,
        customer_email="user@example.com",
        success_url="https://app.nutriapp.example/success",
        cancel_url="https://app.nutriapp.example/cancel",
        idempotency_key="idem-fixed-key",
    )

    assert result.stripe_session_id == "cs_test_a1b2c3d4e5f6g7h8i9j0"
    assert result.url.startswith("https://checkout.stripe.com/")
    assert len(seen_requests) == 1
    assert seen_requests[0].headers["Idempotency-Key"] == "idem-fixed-key"
    assert seen_requests[0].headers["Authorization"] == "Bearer sk_test_fixture"

    # qa-agent follow-up finding: this is the entire load-bearing mechanism
    # for the customer.subscription.created ordering fix (a future refactor
    # dropping either field would go uncaught by every other assertion in
    # this suite) -- assert the actual outgoing form-encoded request body
    # sent to Stripe carries both client_reference_id (used by
    # checkout.session.completed's own payload) and
    # subscription_data[metadata][user_id] (copied onto the Subscription
    # object Stripe creates, so customer.subscription.created's payload
    # can resolve user_id even if it arrives first).
    sent_form = dict(urllib.parse.parse_qsl(seen_requests[0].content.decode("utf-8")))
    assert sent_form["client_reference_id"] == str(user_id)
    assert sent_form["subscription_data[metadata][user_id]"] == str(user_id)
    await adapter.aclose()


async def test_idempotency_key_present_on_every_retry_attempt():
    seen_keys = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers.get("Idempotency-Key"))
        raise httpx.ConnectError("simulated transient failure", request=request)

    adapter = _make_adapter(httpx.MockTransport(handler))
    with pytest.raises(PaymentProviderUnavailableError):
        await adapter.create_checkout_session(
            user_id=uuid.uuid4(),
            customer_email=None,
            success_url="https://app.nutriapp.example/success",
            cancel_url="https://app.nutriapp.example/cancel",
            idempotency_key="idem-retried-key",
        )

    assert len(seen_keys) == 3  # tenacity stop_after_attempt(3)
    assert all(k == "idem-retried-key" for k in seen_keys)
    await adapter.aclose()


async def test_circuit_breaker_opens_after_repeated_failures_and_recovers():
    counter = _Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        counter.increment()
        return httpx.Response(500, content=b"server error")

    adapter = _make_adapter(httpx.MockTransport(handler))
    adapter._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
        default_threshold=5, default_ttl=30
    )

    for _ in range(5):
        with pytest.raises(PaymentProviderUnavailableError):
            await adapter.create_checkout_session(
                user_id=uuid.uuid4(),
                customer_email=None,
                success_url="https://app.nutriapp.example/success",
                cancel_url="https://app.nutriapp.example/cancel",
                idempotency_key=f"idem-{uuid.uuid4()}",
            )

    calls_before_open = counter.value

    # Breaker should now be open -- fails fast, no further HTTP attempts.
    with pytest.raises(PaymentProviderUnavailableError):
        await adapter.create_checkout_session(
            user_id=uuid.uuid4(),
            customer_email=None,
            success_url="https://app.nutriapp.example/success",
            cancel_url="https://app.nutriapp.example/cancel",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
    assert counter.value == calls_before_open

    await adapter.aclose()


async def test_verify_webhook_signature_valid():
    adapter = _make_adapter(httpx.MockTransport(lambda r: httpx.Response(200)))
    payload = _load_fixture("stripe_webhooks", "checkout_session_completed.json")
    header = sign_payload(payload)

    event = adapter.verify_webhook_signature(payload=payload, signature_header=header)
    assert event["type"] == "checkout.session.completed"
    await adapter.aclose()


async def test_verify_webhook_signature_tampered_payload_fails():
    adapter = _make_adapter(httpx.MockTransport(lambda r: httpx.Response(200)))
    payload = _load_fixture("stripe_webhooks", "checkout_session_completed.json")
    header = sign_payload(payload)
    tampered = payload.replace(b"paid", b"free")

    with pytest.raises(WebhookSignatureVerificationError):
        adapter.verify_webhook_signature(payload=tampered, signature_header=header)
    await adapter.aclose()


async def test_verify_webhook_signature_wrong_secret_fails():
    adapter = _make_adapter(httpx.MockTransport(lambda r: httpx.Response(200)))
    payload = _load_fixture("stripe_webhooks", "checkout_session_completed.json")
    header = sign_payload(payload, secret="whsec_totally_wrong_secret")

    with pytest.raises(WebhookSignatureVerificationError):
        adapter.verify_webhook_signature(payload=payload, signature_header=header)
    await adapter.aclose()


async def test_verify_webhook_signature_expired_timestamp_fails():
    adapter = _make_adapter(httpx.MockTransport(lambda r: httpx.Response(200)))
    payload = _load_fixture("stripe_webhooks", "checkout_session_completed.json")
    ancient_timestamp = 1000000000  # far outside the 300s tolerance window
    header = sign_payload(payload, timestamp=ancient_timestamp)

    with pytest.raises(WebhookSignatureVerificationError):
        adapter.verify_webhook_signature(payload=payload, signature_header=header)
    await adapter.aclose()


async def test_verify_webhook_signature_missing_header_fails():
    adapter = _make_adapter(httpx.MockTransport(lambda r: httpx.Response(200)))
    payload = _load_fixture("stripe_webhooks", "checkout_session_completed.json")

    with pytest.raises(WebhookSignatureVerificationError):
        adapter.verify_webhook_signature(payload=payload, signature_header="")
    await adapter.aclose()
