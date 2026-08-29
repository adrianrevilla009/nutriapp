"""EntitlementGranted (v1) -- see docs/events-catalog.md.

The event `recipe-service`/`social-service`/`analytics-service` actually
cache a local entitlement flag from (docs/domain-glossary-and-context-map.md's
Open Host Service relationship; `ProUpgradeEntitlementPropagation` saga,
docs/sagas-and-distributed-transactions.md). `aggregate_id` is the
`user_id`, not the `subscription_id` -- entitlement is a per-user derived
flag, not itself a persisted aggregate of its own in this service's
event-driven-CRUD model (ADR-0002); keying by user_id matches how every
consumer actually caches it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "EntitlementGranted"
EVENT_VERSION = 1


def build_entitlement_granted_event(
    *, user_id: uuid.UUID, correlation_id: str, causation_id: str | None = None
) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "reason": "subscription_started",
        "granted_at": datetime.now(timezone.utc).isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=EventMetadata(
            correlation_id=correlation_id, user_id=str(user_id), causation_id=causation_id
        ),
    )
