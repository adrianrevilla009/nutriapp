"""PasswordResetRequested (v1, new) — see docs/events-catalog.md."""

from __future__ import annotations

import uuid

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "PasswordResetRequested"
EVENT_VERSION = 1


def build_password_reset_requested_event(
    *,
    user_id: uuid.UUID,
    email: str,
    reset_token_reference_id: uuid.UUID,
    requested_at_iso: str,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload={
            "user_id": str(user_id),
            "email": email,
            "reset_token_reference_id": str(reset_token_reference_id),
            "requested_at": requested_at_iso,
        },
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
    )
