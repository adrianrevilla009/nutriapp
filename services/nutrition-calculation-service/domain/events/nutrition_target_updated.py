"""NutritionTargetUpdated (v1) -- see docs/events-catalog.md and
implementation plan section 5. Emitted whenever a user's calculated
calorie/macro target changes. `activity_adjustment_kcal` is always `None`
this pass (reserved seam for activity-service, implementation plan
section 1, item 2).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from domain.events.base import DomainEvent, EventMetadata
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange

EVENT_TYPE = "NutritionTargetUpdated"
EVENT_VERSION = 1

TargetUpdateReason = Literal[
    "weight_recorded", "body_metric_recorded", "goal_set", "goal_updated", "formula_correction"
]


def build_nutrition_target_updated_event(
    *,
    user_id: uuid.UUID,
    bmr_kcal: float,
    tdee_kcal: float,
    calorie_target_kcal: float,
    macro_targets: MacroTargetRange,
    goal_type: GoalType,
    activity_level: ActivityLevel,
    clamped: bool,
    clamp_reason: str | None,
    formula_version: str,
    reason: TargetUpdateReason,
    effective_from: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "bmr_kcal": bmr_kcal,
        "tdee_kcal": tdee_kcal,
        "calorie_target_kcal": calorie_target_kcal,
        "macro_targets": {
            "protein_g_min": macro_targets.protein_g_min,
            "protein_g_max": macro_targets.protein_g_max,
            "fat_g_min": macro_targets.fat_g_min,
            "carbs_g": macro_targets.carbs_g,
        },
        "goal_type": goal_type.value,
        "activity_level": activity_level.value,
        "activity_adjustment_kcal": None,
        "clamped": clamped,
        "clamp_reason": clamp_reason,
        "formula_version": formula_version,
        "reason": reason,
        "effective_from": effective_from.isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
        occurred_at=effective_from,
    )
