"""POST /internal/v1/billing/webhooks/stripe -- Stripe webhook receiver
(implementation plan section 1.2).

Deliberately NOT actually "internal" in the Kong-routing sense despite the
`/internal/v1` path prefix every other service's non-Kong-routed endpoint
uses: Stripe itself must be able to reach this endpoint over the public
internet (Stripe's own documented requirement for webhook endpoints), so
Kong DOES route this one path publicly. It is still never JWT-gated --
authenticity is instead verified via the `Stripe-Signature` HMAC scheme
(implementation plan section 1.2/section 9 risk 1; documented again in
README.md and the Helm chart/Kong config comments so a future reviewer
does not mistake this for a missing-auth bug).

Idempotent (dedupe by Stripe's own event `id`) and signature-verified
before any processing -- never trust an unverified payload. A recognized-
but-unhandled event type (e.g. `customer.updated`) returns 200 with no
side effect, never a 4xx/5xx -- Stripe expects a 2xx to stop retrying an
event this service simply doesn't act on.

Five handled event types (reviewer-agent finding, this session's fix
adds the 5th): `checkout.session.completed`, `customer.subscription.created`,
`invoice.paid`, `customer.subscription.deleted`, `invoice.payment_failed`.
`customer.subscription.created` is consumed specifically because Stripe's
real `checkout.session.completed` payload never carries the new
subscription's `current_period_end` (only the Subscription object's own
webhook payload does) -- see `PRO_TIER_BILLING_PERIOD_END_ESTIMATE_DAYS`'s
docstring and `application/commands/handle_subscription_created.py` for
the full ordering-safety design (Stripe does not strictly order these two
events relative to each other).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_checkout_completed import (
    HandleCheckoutCompletedCommand,
    HandleCheckoutCompletedHandler,
)
from application.commands.handle_invoice_paid import (
    HandleInvoicePaidCommand,
    HandleInvoicePaidHandler,
)
from application.commands.handle_payment_failed import (
    HandlePaymentFailedCommand,
    HandlePaymentFailedHandler,
)
from application.commands.handle_subscription_created import (
    HandleSubscriptionCreatedCommand,
    HandleSubscriptionCreatedHandler,
)
from application.commands.handle_subscription_deleted import (
    HandleSubscriptionDeletedCommand,
    HandleSubscriptionDeletedHandler,
)
from domain.value_objects.stripe_ids import StripeCustomerId, StripeSubscriptionId
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import get_container, get_correlation_id, get_session
from infrastructure.http.error_mapping import map_exception

router = APIRouter(prefix="/internal/v1/billing", tags=["webhooks"])

# Best-effort PLACEHOLDER only, used by HandleCheckoutCompletedHandler
# solely when no subscription row exists yet for this stripe_subscription_id
# (i.e. checkout.session.completed happens to arrive before
# customer.subscription.created) -- corrected to the real value moments
# later once customer.subscription.created's own payload (which DOES
# carry the authoritative current_period_end) is processed. Never trusted
# as final; PaymentProviderPort intentionally still has exactly two
# operations (create_checkout_session, verify_webhook_signature) -- this
# estimate avoids needing a third "retrieve subscription" outbound call,
# per architecture-agent's confirmed port-scoping reasoning.
PRO_TIER_BILLING_PERIOD_END_ESTIMATE_DAYS = 30


def _from_unix(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


@router.post(
    "/webhooks/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook receiver (public, signature-verified, never JWT-gated)",
)
async def receive_stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
) -> JSONResponse:
    raw_body = await request.body()
    try:
        event = container.payment_provider.verify_webhook_signature(
            payload=raw_body, signature_header=stripe_signature
        )
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)

    event_type = event.get("type", "")
    event_id = event.get("id", "")
    data_object: dict[str, Any] = event.get("data", {}).get("object", {})
    now = datetime.now(timezone.utc)

    subscriptions, processed_events, revocation_schedule, outbox = build_repositories(session)

    try:
        if event_type == "checkout.session.completed":
            checkout_completed_handler = HandleCheckoutCompletedHandler(
                subscriptions, processed_events, outbox
            )
            await checkout_completed_handler.handle(
                HandleCheckoutCompletedCommand(
                    stripe_event_id=event_id,
                    user_id=uuid.UUID(data_object["client_reference_id"]),
                    stripe_customer_id=StripeCustomerId(data_object["customer"]),
                    stripe_subscription_id=StripeSubscriptionId(data_object["subscription"]),
                    current_period_end_estimate=now
                    + timedelta(days=PRO_TIER_BILLING_PERIOD_END_ESTIMATE_DAYS),
                    correlation_id=correlation_id,
                    now=now,
                )
            )
        elif event_type == "customer.subscription.created":
            subscription_created_handler = HandleSubscriptionCreatedHandler(
                subscriptions, processed_events
            )
            await subscription_created_handler.handle(
                HandleSubscriptionCreatedCommand(
                    stripe_event_id=event_id,
                    user_id=uuid.UUID(data_object["metadata"]["user_id"]),
                    stripe_customer_id=StripeCustomerId(data_object["customer"]),
                    stripe_subscription_id=StripeSubscriptionId(data_object["id"]),
                    current_period_end=_from_unix(data_object["current_period_end"]),
                    now=now,
                )
            )
        elif event_type == "invoice.paid":
            invoice_paid_handler = HandleInvoicePaidHandler(subscriptions, processed_events, outbox)
            await invoice_paid_handler.handle(
                HandleInvoicePaidCommand(
                    stripe_event_id=event_id,
                    stripe_subscription_id=StripeSubscriptionId(data_object["subscription"]),
                    new_current_period_end=_from_unix(data_object["period_end"]),
                    correlation_id=correlation_id,
                    now=now,
                )
            )
        elif event_type == "customer.subscription.deleted":
            subscription_deleted_handler = HandleSubscriptionDeletedHandler(
                subscriptions, processed_events, outbox, revocation_schedule
            )
            await subscription_deleted_handler.handle(
                HandleSubscriptionDeletedCommand(
                    stripe_event_id=event_id,
                    stripe_subscription_id=StripeSubscriptionId(data_object["id"]),
                    correlation_id=correlation_id,
                    now=now,
                )
            )
        elif event_type == "invoice.payment_failed":
            payment_failed_handler = HandlePaymentFailedHandler(
                subscriptions, processed_events, outbox
            )
            await payment_failed_handler.handle(
                HandlePaymentFailedCommand(
                    stripe_event_id=event_id,
                    stripe_subscription_id=StripeSubscriptionId(data_object["subscription"]),
                    correlation_id=correlation_id,
                    now=now,
                )
            )
        else:
            # Recognized-but-unhandled event type -- 200, no side effect,
            # per Stripe's own "return 2xx to stop retries" expectation.
            await session.commit()
            return JSONResponse(status_code=status.HTTP_200_OK, content=_ack(event_type))
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)

    return JSONResponse(status_code=status.HTTP_200_OK, content=_ack(event_type))


def _ack(event_type: str) -> dict[str, str]:
    body: dict[str, str] = {}
    body["received"] = "true"
    body["event_type"] = event_type
    return body
