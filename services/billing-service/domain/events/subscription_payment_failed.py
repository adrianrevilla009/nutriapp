"""SubscriptionPaymentFailed (v1) -- see docs/events-catalog.md.

Emitted from `invoice.payment_failed`. Entitlement is NOT revoked by this
event alone -- Stripe's own dunning/retry window determines if/when the
subscription is ultimately canceled (a later `customer.subscription.deleted`
webhook, handled separately).
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.entities.subscription import Subscription
from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "SubscriptionPaymentFailed"
EVENT_VERSION = 1


def build_subscription_payment_failed_event(
    *, subscription: Subscription, correlation_id: str
) -> DomainEvent:
    payload = {
        "subscription_id": str(subscription.subscription_id),
        "user_id": str(subscription.user_id),
        "stripe_subscription_id": str(subscription.stripe_subscription_id),
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(subscription.subscription_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(subscription.user_id)),
    )
