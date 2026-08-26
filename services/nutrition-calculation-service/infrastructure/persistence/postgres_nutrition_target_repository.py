"""PostgresNutritionTargetRepository -- implements NutritionTargetRepositoryPort.
Upsert-by-`user_id` (implementation plan section 2: one row per user)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.nutrition_target import NutritionTarget
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant
from infrastructure.persistence.models import NutritionTargetModel


def _to_domain(row: NutritionTargetModel) -> NutritionTarget:
    return NutritionTarget(
        user_id=row.user_id,
        bmr_kcal=row.bmr_kcal,
        tdee_kcal=row.tdee_kcal,
        calorie_target_kcal=row.calorie_target_kcal,
        macro_targets=MacroTargetRange(
            protein_g_min=row.protein_g_min,
            protein_g_max=row.protein_g_max,
            fat_g_min=row.fat_g_min,
            carbs_g=row.carbs_g,
            carbs_floored=row.carbs_floored,
        ),
        goal_type=GoalType(row.goal_type),
        activity_level=ActivityLevel(row.activity_level),
        sex_constant_used=CalculationSexConstant(row.sex_constant_used),
        clamped=row.clamped,
        clamp_reason=row.clamp_reason,
        formula_version=row.formula_version,
        reason=row.reason,
        effective_from=row.effective_from,
    )


class PostgresNutritionTargetRepository:
    """Implements domain.ports.nutrition_target_repository_port.NutritionTargetRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_current(self, user_id: uuid.UUID) -> NutritionTarget | None:
        row = await self._session.get(NutritionTargetModel, user_id)
        return _to_domain(row) if row is not None else None

    async def upsert(self, target: NutritionTarget) -> None:
        row = await self._session.get(NutritionTargetModel, target.user_id)
        if row is None:
            row = NutritionTargetModel(user_id=target.user_id)
            self._session.add(row)
        row.bmr_kcal = target.bmr_kcal
        row.tdee_kcal = target.tdee_kcal
        row.calorie_target_kcal = target.calorie_target_kcal
        row.protein_g_min = target.macro_targets.protein_g_min
        row.protein_g_max = target.macro_targets.protein_g_max
        row.fat_g_min = target.macro_targets.fat_g_min
        row.carbs_g = target.macro_targets.carbs_g
        row.carbs_floored = target.macro_targets.carbs_floored
        row.goal_type = target.goal_type.value
        row.activity_level = target.activity_level.value
        row.sex_constant_used = target.sex_constant_used.value
        row.clamped = target.clamped
        row.clamp_reason = target.clamp_reason
        row.formula_version = target.formula_version
        row.reason = target.reason
        row.effective_from = target.effective_from
        await self._session.flush()
