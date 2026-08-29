"""SubscriptionRenewed (v1) -- see docs/events-catalog.md.

Emitted from `invoice.paid` for an existing subscription: the paid period
was extended.
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.entities.subscription import Subscription
from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "SubscriptionRenewed"
EVENT_VERSION = 1


def build_subscription_renewed_event(
    *, subscription: Subscription, correlation_id: str
) -> DomainEvent:
    payload = {
        "subscription_id": str(subscription.subscription_id),
        "user_id": str(subscription.user_id),
        "stripe_subscription_id": str(subscription.stripe_subscription_id),
        "current_period_end": subscription.current_period_end.isoformat(),
        "renewed_at": datetime.now(timezone.utc).isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(subscription.subscription_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(subscription.user_id)),
    )
