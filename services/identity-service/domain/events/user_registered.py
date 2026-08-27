"""UserRegistered (v1) — see docs/events-catalog.md.

Additive change in this plan: payload gains
`email_verification_token_reference_id` (reference id only, never the raw
verification secret — implementation plan section 5).
"""

from __future__ import annotations

import uuid

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "UserRegistered"
EVENT_VERSION = 1  # additive field only — not a breaking change, no version bump


def build_user_registered_event(
    *,
    user_id: uuid.UUID,
    email: str,
    registered_at_iso: str,
    email_verification_token_reference_id: uuid.UUID,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload={
            "user_id": str(user_id),
            "email": email,
            "registered_at": registered_at_iso,
            "email_verification_token_reference_id": str(email_verification_token_reference_id),
        },
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
    )
