"""PaymentProviderPort -- the only boundary through which this service
talks to a third-party payment provider (Stripe, ADR-0015). The domain
never imports Stripe's SDK directly (ADR-0001); `StripePaymentAdapter`
(infrastructure/external/stripe_payment_adapter.py) is the sole adapter.

Two operations only, per implementation plan section 1/§3 scope:
- `create_checkout_session` -- creates a Stripe-hosted Checkout Session
  (PCI scope minimization: card data goes directly from the client to
  Stripe, never through this service -- `.claude/agents/billing-agent.md`).
- `verify_webhook_signature` -- Stripe's documented `Stripe-Signature`
  HMAC scheme, a local computation (no network call), so it needs no
  circuit breaker of its own (implementation plan section 7).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    stripe_session_id: str
    url: str


class PaymentProviderError(Exception):
    """Base class for every error this port's adapter can raise."""


class PaymentProviderUnavailableError(PaymentProviderError):
    """Raised when Stripe's Checkout Session creation call fails after
    retries, or the `stripe_checkout` circuit breaker is open."""


class WebhookSignatureVerificationError(PaymentProviderError):
    """Raised for a missing/malformed/tampered/wrong-secret/expired-
    timestamp `Stripe-Signature` header -- never trust an unverified
    webhook payload (implementation plan section 1.2)."""


class PaymentProviderPort(Protocol):
    async def create_checkout_session(
        self,
        *,
        user_id: uuid.UUID,
        customer_email: str | None,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> CheckoutSession: ...

    def verify_webhook_signature(self, *, payload: bytes, signature_header: str) -> dict[str, Any]:
        """Returns the parsed, verified Stripe event object (a plain
        dict -- this port never leaks the Stripe SDK's own event type past
        this boundary). Raises `WebhookSignatureVerificationError` for any
        verification failure."""
        ...
