"""NewDeviceLoginDetected (v1, new) — see docs/events-catalog.md."""
from __future__ import annotations

import uuid

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "NewDeviceLoginDetected"
EVENT_VERSION = 1


def build_new_device_login_detected_event(
    *,
    user_id: uuid.UUID,
    device_fingerprint_hash: str,
    occurred_at_iso: str,
    email: str,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload={
            "user_id": str(user_id),
            "device_fingerprint_hash": device_fingerprint_hash,
            "occurred_at": occurred_at_iso,
            "email": email,
        },
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
    )
