"""StripePaymentAdapter -- implements PaymentProviderPort (ADR-0015:
Stripe). Built against Stripe's actual, publicly documented API contract
(Checkout Sessions: https://stripe.com/docs/api/checkout/sessions,
webhook signing: https://stripe.com/docs/webhooks/signatures) -- tested
entirely via fixtures/mocks, never a live call (implementation plan
section 1's provider-approach note).

Two operations only, matching `PaymentProviderPort`:
- `create_checkout_session` -- one outbound HTTP call to Stripe's REST
  API (form-urlencoded body, `Authorization: Bearer <secret key>`,
  `Idempotency-Key` header per Stripe's documented retry-safety scheme --
  never a body param). Own, dedicated purgatory circuit breaker
  (`stripe_checkout`), tenacity retry (transport-level failures only,
  reusing the SAME idempotency key across every attempt so a retried
  create-call can't accidentally create two sessions), own httpx.AsyncClient
  (bulkhead), explicit timeout.
- `verify_webhook_signature` -- LOCAL HMAC-SHA256 computation against the
  documented `Stripe-Signature: t=<timestamp>,v1=<signature>[,v1=...]`
  header scheme. No network call, so no circuit breaker.

PCI scope minimization (billing-agent.md): this adapter never receives or
forwards raw card/payment-method data -- it only ever sends the fields
Stripe's Checkout Session creation call documents (price id, urls,
customer email, client_reference_id) and receives back a hosted Checkout
URL. Card data goes directly from the client's browser to Stripe.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import httpx
import purgatory
import structlog
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.payment_provider_port import (
    CheckoutSession,
    PaymentProviderUnavailableError,
    WebhookSignatureVerificationError,
)

logger = structlog.get_logger()

CIRCUIT_NAME = "stripe_checkout"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
DEFAULT_SIGNATURE_TOLERANCE_SECONDS = 300


class StripePaymentAdapter:
    """Implements domain.ports.payment_provider_port.PaymentProviderPort."""

    def __init__(
        self,
        *,
        secret_key: str,
        webhook_signing_secret: str,
        price_id: str,
        base_url: str = "https://api.stripe.com",
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
        signature_tolerance_seconds: int = DEFAULT_SIGNATURE_TOLERANCE_SECONDS,
    ) -> None:
        self._secret_key = secret_key
        self._webhook_signing_secret = webhook_signing_secret
        self._price_id = price_id
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )
        self._signature_tolerance_seconds = signature_tolerance_seconds

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _post_checkout_session(
        self, form_body: dict[str, str], idempotency_key: str
    ) -> httpx.Response:
        headers = _auth_headers(self._secret_key, idempotency_key)
        return await self._http.post(
            f"{self._base_url}/v1/checkout/sessions", data=form_body, headers=headers
        )

    async def create_checkout_session(
        self,
        *,
        user_id: uuid.UUID,
        customer_email: str | None,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> CheckoutSession:
        form_body = _build_checkout_session_form_body(
            price_id=self._price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            user_id=user_id,
            customer_email=customer_email,
        )

        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._post_checkout_session(form_body, idempotency_key)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise PaymentProviderUnavailableError("Stripe checkout circuit is open.") from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise PaymentProviderUnavailableError(
                f"Stripe checkout session creation failed: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise PaymentProviderUnavailableError(
                f"Stripe rejected the checkout session creation ({response.status_code})."
            )

        body = response.json()
        return CheckoutSession(stripe_session_id=body["id"], url=body["url"])

    def verify_webhook_signature(self, *, payload: bytes, signature_header: str) -> dict[str, Any]:
        timestamp, signatures = _parse_signature_header(signature_header)
        if timestamp is None or not signatures:
            raise WebhookSignatureVerificationError("Missing or malformed Stripe-Signature header.")

        now = int(time.time())
        if abs(now - timestamp) > self._signature_tolerance_seconds:
            raise WebhookSignatureVerificationError(
                "Webhook timestamp is outside the allowed tolerance window "
                f"(possible replay attack): {timestamp}."
            )

        signed_payload = f"{timestamp}.".encode("ascii") + payload
        expected_signature = hmac.new(
            self._webhook_signing_secret.encode("utf-8"), signed_payload, hashlib.sha256
        ).hexdigest()

        if not any(hmac.compare_digest(expected_signature, sig) for sig in signatures):
            raise WebhookSignatureVerificationError("Signature verification failed.")

        try:
            parsed: dict[str, Any] = json.loads(payload)
            return parsed
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WebhookSignatureVerificationError(
                f"Verified payload is not valid JSON: {exc}"
            ) from exc

    async def aclose(self) -> None:
        await self._http.aclose()


def _auth_headers(secret_key: str, idempotency_key: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    headers["Authorization"] = f"Bearer {secret_key}"
    headers["Idempotency-Key"] = idempotency_key
    return headers


def _build_checkout_session_form_body(
    *,
    price_id: str,
    success_url: str,
    cancel_url: str,
    user_id: uuid.UUID,
    customer_email: str | None,
) -> dict[str, str]:
    # Stripe's Checkout Session creation call is form-urlencoded, not JSON
    # (https://stripe.com/docs/api/checkout/sessions/create) --
    # `line_items[0][...]`'s bracket notation is Stripe's own documented
    # array-encoding convention for form bodies.
    form_body: dict[str, str] = {}
    form_body["mode"] = "subscription"
    form_body["line_items[0][price]"] = price_id
    form_body["line_items[0][quantity]"] = "1"
    form_body["success_url"] = success_url
    form_body["cancel_url"] = cancel_url
    form_body["client_reference_id"] = str(user_id)
    # Copied onto the Subscription object Stripe creates from this
    # Checkout Session (Stripe's own documented `subscription_data.metadata`
    # passthrough) -- lets `customer.subscription.created`'s webhook
    # payload (which has no `client_reference_id` of its own; that field
    # only exists on Checkout Session objects) still resolve the owning
    # `user_id`, even if that event arrives BEFORE `checkout.session.completed`
    # (reviewer-agent finding, ordering-safety fix).
    form_body["subscription_data[metadata][user_id]"] = str(user_id)
    if customer_email:
        form_body["customer_email"] = customer_email
    return form_body


def _parse_signature_header(header: str) -> tuple[int | None, list[str]]:
    """Parses Stripe's `t=<timestamp>,v1=<signature>[,v1=<signature>...]`
    format (https://stripe.com/docs/webhooks/signatures#verify-manually).
    Multiple `v1=` entries occur during a webhook signing-secret rotation
    window -- any one matching is sufficient."""
    timestamp: int | None = None
    signatures: list[str] = []
    for item in header.split(","):
        item = item.strip()
        if "=" not in item:
            continue
        key, _, value = item.partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                timestamp = None
        elif key == "v1":
            signatures.append(value)
    return timestamp, signatures
