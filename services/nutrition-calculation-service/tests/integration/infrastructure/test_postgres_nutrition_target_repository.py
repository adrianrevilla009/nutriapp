from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.nutrition_target import NutritionTarget
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant
from infrastructure.persistence.postgres_nutrition_target_repository import (
    PostgresNutritionTargetRepository,
)


def _make_target(user_id: uuid.UUID, calorie_target_kcal: float = 2093.0) -> NutritionTarget:
    return NutritionTarget(
        user_id=user_id,
        bmr_kcal=1673.75,
        tdee_kcal=2593.0,
        calorie_target_kcal=calorie_target_kcal,
        macro_targets=MacroTargetRange(
            protein_g_min=112.0,
            protein_g_max=154.0,
            fat_g_min=46.5,
            carbs_g=200.0,
            carbs_floored=False,
        ),
        goal_type=GoalType.LOSE,
        activity_level=ActivityLevel.MODERATE,
        sex_constant_used=CalculationSexConstant.MALE,
        clamped=False,
        clamp_reason=None,
        formula_version="2026.1",
        reason="weight_recorded",
        effective_from=datetime.now(timezone.utc),
    )


async def test_upsert_by_user_id_round_trip(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresNutritionTargetRepository(session)
        assert await repo.get_current(user_id) is None
        await repo.upsert(_make_target(user_id))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresNutritionTargetRepository(session)
        fetched = await repo.get_current(user_id)
        assert fetched is not None
        assert fetched.calorie_target_kcal == 2093.0

        await repo.upsert(_make_target(user_id, calorie_target_kcal=1800.0))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresNutritionTargetRepository(session)
        fetched = await repo.get_current(user_id)
        assert fetched.calorie_target_kcal == 1800.0
