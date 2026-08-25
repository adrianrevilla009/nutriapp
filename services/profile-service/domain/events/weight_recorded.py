"""WeightRecorded (v1) -- see docs/events-catalog.md.

Payload built here at the domain layer carries the PLAINTEXT weight_kg
value (the domain layer has zero I/O -- no KMS calls, ADR-0001). The
application-layer command handler is responsible for producing an
encrypted-payload copy (via DomainEvent.with_payload + DataEncryptionPort)
before this event is appended to the event store / outbox -- see
application/commands/record_weight.py. Only the encrypted copy is ever
persisted or published.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "WeightRecorded"
EVENT_VERSION = 1


def build_weight_recorded_event(
    user_id: uuid.UUID, weight_kg: float, recorded_at: datetime, correlation_id: str
) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "weight_kg": weight_kg,
        "recorded_at": recorded_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=metadata,
    )
