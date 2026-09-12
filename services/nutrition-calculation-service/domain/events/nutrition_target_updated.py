"""NutritionTargetUpdated (v1) -- see docs/events-catalog.md and
implementation plan section 5. Emitted whenever a user's calculated
calorie/macro target changes. `activity_adjustment_kcal` is always `None`
this pass (reserved seam for activity-service, implementation plan
section 1, item 2).

`nutrient_targets_min` (added additively, still v1 -- see
docs/events-catalog.md's versioning-decision note on this field, and
`domain/services/nutrient_target_min_builder.py` for the full "what is/
isn't covered" reasoning): a nutrient-keyed minimum-target map, generic
enough for a downstream consumer to key by nutrient name rather than
parsing `macro_targets`. Always contains `protein_g`/`fat_g`; as of Phase
2 (`dri-rda-addendum.md`), also contains `calcium_mg`/`iron_mg`/
`vitamin_c_mg` when the caller passes `micronutrient_targets_min` (the
`RecomputeNutritionTargetHandler`-resolved output of
`domain/services/micronutrient_dri_resolver.py`) -- omitted, never
fabricated, for under-19 users or when the caller has none to pass (e.g.
existing tests that only exercise the macro-only path).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Literal

from domain.events.base import DomainEvent, EventMetadata
from domain.services.nutrient_target_min_builder import build_nutrient_targets_min
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
    micronutrient_targets_min: Mapping[str, float] | None = None,
) -> DomainEvent:
    nutrient_targets_min = {
        **build_nutrient_targets_min(macro_targets),
        **(micronutrient_targets_min or {}),
    }
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
        "nutrient_targets_min": nutrient_targets_min,
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
