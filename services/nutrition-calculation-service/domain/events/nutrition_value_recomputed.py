"""NutritionValueRecomputed (v1) -- see docs/events-catalog.md and
implementation plan section 5. Emitted whenever a user's per-entry or
per-day nutrient total changes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from domain.events.base import DomainEvent, EventMetadata
from domain.value_objects.confidence_range import ConfidenceRange
from domain.value_objects.nutrient_total_line import MacroAmounts, NutrientTotalLine

EVENT_TYPE = "NutritionValueRecomputed"
EVENT_VERSION = 1

RecomputeScope = Literal["entry", "day"]
RecomputeReason = Literal[
    "food_entry_logged", "food_entry_corrected", "food_entry_deleted", "formula_correction"
]


def _macros_payload(macros: MacroAmounts) -> dict[str, float]:
    return {
        "calories_kcal": macros.calories_kcal,
        "protein_g": macros.protein_g,
        "carbs_g": macros.carbs_g,
        "fat_g": macros.fat_g,
    }


def build_nutrition_value_recomputed_event(
    *,
    user_id: uuid.UUID,
    scope: RecomputeScope,
    entry_id: uuid.UUID | None,
    total_date: date | None,
    line: NutrientTotalLine,
    confidence_range: ConfidenceRange | None,
    formula_version: str,
    reason: RecomputeReason,
    correlation_id: str,
    recomputed_at: datetime,
) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "scope": scope,
        "entry_id": str(entry_id) if entry_id is not None else None,
        "date": total_date.isoformat() if total_date is not None else None,
        "macros": _macros_payload(line.macros),
        "micronutrients": dict(line.micronutrients) if line.micronutrients is not None else None,
        "micronutrients_status": line.micronutrients_status,
        "is_estimated": line.is_estimated,
        "confidence_range": (
            {"min": confidence_range.min, "max": confidence_range.max}
            if confidence_range is not None
            else None
        ),
        "formula_version": formula_version,
        "reason": reason,
        "recomputed_at": recomputed_at.isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
        occurred_at=recomputed_at,
    )
