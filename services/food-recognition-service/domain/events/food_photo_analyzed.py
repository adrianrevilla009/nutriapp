"""FoodPhotoAnalyzed (v1) -- see docs/events-catalog.md and implementation
plan section 5. Published via the Outbox after EVERY photo analysis
attempt, including failed/unavailable ones (a run of failures is itself a
signal worth having in the event stream, distinguishable by `status`).

Audit/traceability record only -- never consumed synchronously by
anything to auto-write to `diary-service`. The actual diary entry is
created by the user's own subsequent, ordinary `diary-service` log call,
referencing this event's `aggregate_id` (the analysis id) in its own
`correlation_id` for traceability (media-recognition-conventions
SKILL.md's "never auto-write" rule).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata
from domain.value_objects.analysis_status import AnalysisStatus
from domain.value_objects.food_candidate import FoodCandidate

EVENT_TYPE = "FoodPhotoAnalyzed"
EVENT_VERSION = 1


def _candidate_payload(candidate: FoodCandidate) -> dict[str, object]:
    return {
        "name": candidate.name,
        "portion_range_min_g": candidate.portion_range.min_g,
        "portion_range_max_g": candidate.portion_range.max_g,
        "confidence": candidate.confidence.value,
    }


def build_food_photo_analyzed_event(
    *,
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
    candidates: list[FoodCandidate],
    model_version: str,
    status: AnalysisStatus,
    correlation_id: str,
    occurred_at: datetime,
) -> DomainEvent:
    payload = {
        "analysis_id": str(analysis_id),
        "candidates": [_candidate_payload(candidate) for candidate in candidates],
        "model_version": model_version,
        "status": status,
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(analysis_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
        occurred_at=occurred_at,
    )
