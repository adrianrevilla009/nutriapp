"""NutritionTarget -- the current calorie/macro target aggregate.

Conventional persistence (ADR-0002, not event-sourced): the
`nutrition_targets` table's in-memory shape (one row per user, upsert by
`user_id`); every recompute also appends an immutable copy to
`nutrition_target_history` (the append-only timeline, implementation plan
section 2).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant


@dataclass(frozen=True, slots=True)
class NutritionTarget:
    user_id: uuid.UUID
    bmr_kcal: float
    tdee_kcal: float
    calorie_target_kcal: float
    macro_targets: MacroTargetRange
    goal_type: GoalType
    activity_level: ActivityLevel
    sex_constant_used: CalculationSexConstant
    clamped: bool
    clamp_reason: str | None
    formula_version: str
    reason: str
    effective_from: datetime
