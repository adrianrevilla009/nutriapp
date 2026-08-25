"""BiometricConsentGranted (v1) -- see docs/events-catalog.md.

Records explicit, specific consent to collect biometric/health data
(CLAUDE.md section 8) -- required before any metric-recording event can be
produced. Not bundled with general ToS acceptance.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "BiometricConsentGranted"
EVENT_VERSION = 1


def build_biometric_consent_granted_event(
    user_id: uuid.UUID, granted_at: datetime, correlation_id: str
) -> DomainEvent:
    payload = {"user_id": str(user_id), "granted_at": granted_at.isoformat()}
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=metadata,
    )
