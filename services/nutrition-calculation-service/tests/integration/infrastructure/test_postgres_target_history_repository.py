from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.nutrition_target import NutritionTarget
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant
from infrastructure.persistence.postgres_target_history_repository import (
    PostgresTargetHistoryRepository,
)


def _make_target(user_id: uuid.UUID, effective_from: datetime) -> NutritionTarget:
    return NutritionTarget(
        user_id=user_id,
        bmr_kcal=1673.75,
        tdee_kcal=2593.0,
        calorie_target_kcal=2093.0,
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
        effective_from=effective_from,
    )


async def test_append_only_insert_ordered_read(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        repo = PostgresTargetHistoryRepository(session)
        await repo.append(_make_target(user_id, now - timedelta(days=2)))
        await repo.append(_make_target(user_id, now - timedelta(days=1)))
        await repo.append(_make_target(user_id, now))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresTargetHistoryRepository(session)
        history = await repo.list_history(user_id)

    assert len(history) == 3
    assert history[0].effective_from < history[1].effective_from < history[2].effective_from
