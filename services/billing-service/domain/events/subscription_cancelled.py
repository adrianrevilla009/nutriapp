"""SubscriptionCancelled (v1) -- see docs/events-catalog.md.

Emitted from `customer.subscription.deleted`, immediately (unlike
`EntitlementRevoked`, which is deferred to `current_period_end` --
billing-agent.md's explicit rule, implementation plan section 1.5). This
event records the cancellation as a fact that happened now; it does NOT
imply the user has already lost access.
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.entities.subscription import Subscription
from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "SubscriptionCancelled"
EVENT_VERSION = 1


def build_subscription_cancelled_event(
    *, subscription: Subscription, correlation_id: str
) -> DomainEvent:
    payload = {
        "subscription_id": str(subscription.subscription_id),
        "user_id": str(subscription.user_id),
        "stripe_subscription_id": str(subscription.stripe_subscription_id),
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "current_period_end": subscription.current_period_end.isoformat(),
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(subscription.subscription_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(subscription.user_id)),
    )
