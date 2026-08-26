"""PostgresTargetHistoryRepository -- implements TargetHistoryRepositoryPort.
Append-only insert, ordered read (implementation plan section 2 -- the
target-history timeline, retention/pruning deferred per section 9.10)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.nutrition_target import NutritionTarget
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant
from infrastructure.persistence.models import NutritionTargetHistoryModel


def _to_domain(row: NutritionTargetHistoryModel) -> NutritionTarget:
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


class PostgresTargetHistoryRepository:
    """Implements domain.ports.target_history_repository_port.TargetHistoryRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, target: NutritionTarget) -> None:
        row = NutritionTargetHistoryModel(
            user_id=target.user_id,
            bmr_kcal=target.bmr_kcal,
            tdee_kcal=target.tdee_kcal,
            calorie_target_kcal=target.calorie_target_kcal,
            protein_g_min=target.macro_targets.protein_g_min,
            protein_g_max=target.macro_targets.protein_g_max,
            fat_g_min=target.macro_targets.fat_g_min,
            carbs_g=target.macro_targets.carbs_g,
            carbs_floored=target.macro_targets.carbs_floored,
            goal_type=target.goal_type.value,
            activity_level=target.activity_level.value,
            sex_constant_used=target.sex_constant_used.value,
            clamped=target.clamped,
            clamp_reason=target.clamp_reason,
            formula_version=target.formula_version,
            reason=target.reason,
            effective_from=target.effective_from,
        )
        self._session.add(row)
        await self._session.flush()

    async def list_history(self, user_id: uuid.UUID) -> list[NutritionTarget]:
        stmt = (
            select(NutritionTargetHistoryModel)
            .where(NutritionTargetHistoryModel.user_id == user_id)
            .order_by(NutritionTargetHistoryModel.effective_from.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]
