"""SubscriptionStarted (v1) -- see docs/events-catalog.md.

Emitted from `checkout.session.completed`: a brand new Pro subscription
was created via Stripe's hosted Checkout.
"""

from __future__ import annotations

from domain.entities.subscription import Subscription
from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "SubscriptionStarted"
EVENT_VERSION = 1


def build_subscription_started_event(
    *, subscription: Subscription, correlation_id: str
) -> DomainEvent:
    payload = {
        "subscription_id": str(subscription.subscription_id),
        "user_id": str(subscription.user_id),
        "stripe_customer_id": str(subscription.stripe_customer_id),
        "stripe_subscription_id": str(subscription.stripe_subscription_id),
        "current_period_end": subscription.current_period_end.isoformat(),
        "started_at": subscription.created_at.isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(subscription.subscription_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(subscription.user_id)),
    )
