"""EntitlementRevoked (v1) -- see docs/events-catalog.md.

Published only when a revocation-schedule row's `revoke_at` is actually
due (`ProcessDueRevocationsHandler`, implementation plan section 1.5) --
never synchronously from the `customer.subscription.deleted` webhook
handler itself. `aggregate_id` is the `user_id`, same rationale as
`EntitlementGranted`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "EntitlementRevoked"
EVENT_VERSION = 1


def build_entitlement_revoked_event(*, user_id: uuid.UUID, correlation_id: str) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "reason": "subscription_cancelled_period_ended",
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
    )
