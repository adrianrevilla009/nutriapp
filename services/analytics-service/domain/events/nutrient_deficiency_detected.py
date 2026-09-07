"""NutrientDeficiencyDetected (v1) -- see docs/events-catalog.md. Published
via Outbox in the same DB transaction as the `anomaly_alerts` row
(implementation plan section 5), triggered by `HandleNutritionValueRecomputedHandler`
after `domain.services.anomaly_detector.evaluate_breach` reports a
sustained breach that is not within the 14-day cooldown
(implementation plan section 9 addendum, resolution 2).

`aggregate_id` is the `user_id` -- a deficiency signal is a per-user fact,
same convention `EntitlementGranted`/`EntitlementRevoked` already use for
a per-user derived flag, not a per-row/per-detection id.

Every consumer-facing rendering of this event (push copy, any future
in-app banner) must carry the "not a medical diagnosis, consult a
professional" disclaimer (resolution 2) -- enforced structurally on the
`DeficiencySignal` value object this builder consumes
(`domain/value_objects/deficiency_signal.py`), not left to the caller's
discipline."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata
from domain.value_objects.deficiency_signal import DeficiencySignal

EVENT_TYPE = "NutrientDeficiencyDetected"
EVENT_VERSION = 1


def build_nutrient_deficiency_detected_event(
    *,
    user_id: uuid.UUID,
    signal: DeficiencySignal,
    detected_at: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "signal": signal.nutrient,
        "window_days": signal.window_days,
        "value": signal.value,
        "target_min": signal.target_min,
        "sample_size": signal.sample_size,
        "disclaimer": signal.disclaimer,
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
        occurred_at=detected_at,
    )
