from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from application.errors import DailyNutritionTotalNotFoundError, NutritionTargetNotFoundError
from application.queries.get_current_daily_total import (
    GetCurrentDailyTotalHandler,
    GetCurrentDailyTotalQuery,
)
from application.queries.get_current_nutrition_target import (
    GetCurrentNutritionTargetHandler,
    GetCurrentNutritionTargetQuery,
)
from application.queries.get_target_history import GetTargetHistoryHandler, GetTargetHistoryQuery
from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.entities.nutrition_target import NutritionTarget
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant
from tests.fixtures.factories import (
    FakeCurrentTargetCache,
    FakeCurrentTotalCache,
    FakeDailyNutritionTotalRepository,
    FakeNutritionTargetRepository,
    FakeTargetHistoryRepository,
)

USER_ID = uuid.uuid4()


def _make_target() -> NutritionTarget:
    return NutritionTarget(
        user_id=USER_ID,
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
        effective_from=datetime.now(timezone.utc),
    )


async def test_get_current_nutrition_target_not_found_raises():
    repo = FakeNutritionTargetRepository()
    handler = GetCurrentNutritionTargetHandler(repo)
    with pytest.raises(NutritionTargetNotFoundError):
        await handler.handle(GetCurrentNutritionTargetQuery(user_id=USER_ID))


async def test_get_current_nutrition_target_returns_dto():
    repo = FakeNutritionTargetRepository()
    target = _make_target()
    await repo.upsert(target)
    handler = GetCurrentNutritionTargetHandler(repo)

    dto = await handler.handle(GetCurrentNutritionTargetQuery(user_id=USER_ID))

    assert dto.calorie_target_kcal == target.calorie_target_kcal
    assert "informational estimate" in dto.disclaimer.lower()


async def test_get_current_daily_total_not_found_raises():
    repo = FakeDailyNutritionTotalRepository()
    handler = GetCurrentDailyTotalHandler(repo)
    with pytest.raises(DailyNutritionTotalNotFoundError):
        await handler.handle(
            GetCurrentDailyTotalQuery(user_id=USER_ID, total_date=date(2026, 8, 25))
        )


async def test_get_current_daily_total_returns_dto():
    repo = FakeDailyNutritionTotalRepository()
    total = DailyNutritionTotal(user_id=USER_ID, total_date=date(2026, 8, 25))
    await repo.upsert(total)
    handler = GetCurrentDailyTotalHandler(repo)

    dto = await handler.handle(
        GetCurrentDailyTotalQuery(user_id=USER_ID, total_date=date(2026, 8, 25))
    )

    assert dto.calories_kcal == 0.0
    assert "informational estimate" in dto.disclaimer.lower()


async def test_get_target_history_returns_dtos_in_order():
    history_repo = FakeTargetHistoryRepository()
    target = _make_target()
    await history_repo.append(target)
    handler = GetTargetHistoryHandler(history_repo)

    dtos = await handler.handle(GetTargetHistoryQuery(user_id=USER_ID))

    assert len(dtos) == 1
    assert dtos[0].calorie_target_kcal == target.calorie_target_kcal


async def test_get_current_nutrition_target_cache_hit_avoids_repository():
    repo = FakeNutritionTargetRepository()
    cache = FakeCurrentTargetCache()
    target = _make_target()
    await cache.set(USER_ID, target)
    handler = GetCurrentNutritionTargetHandler(repo, cache=cache)

    dto = await handler.handle(GetCurrentNutritionTargetQuery(user_id=USER_ID))

    assert dto.calorie_target_kcal == target.calorie_target_kcal
    assert cache.set_calls == 1  # only the pre-seeded set(), not a second one from the handler


async def test_get_current_nutrition_target_cache_miss_populates_cache():
    repo = FakeNutritionTargetRepository()
    cache = FakeCurrentTargetCache()
    target = _make_target()
    await repo.upsert(target)
    handler = GetCurrentNutritionTargetHandler(repo, cache=cache)

    await handler.handle(GetCurrentNutritionTargetQuery(user_id=USER_ID))

    assert cache.set_calls == 1
    assert (await cache.get(USER_ID)) == target


async def test_get_current_daily_total_cache_hit_avoids_repository():
    repo = FakeDailyNutritionTotalRepository()
    cache = FakeCurrentTotalCache()
    total = DailyNutritionTotal(user_id=USER_ID, total_date=date(2026, 8, 25))
    await cache.set(USER_ID, date(2026, 8, 25), total.compute_total())
    handler = GetCurrentDailyTotalHandler(repo, cache=cache)

    dto = await handler.handle(
        GetCurrentDailyTotalQuery(user_id=USER_ID, total_date=date(2026, 8, 25))
    )

    assert dto.calories_kcal == 0.0


async def test_get_current_daily_total_cache_miss_populates_cache():
    repo = FakeDailyNutritionTotalRepository()
    cache = FakeCurrentTotalCache()
    total = DailyNutritionTotal(user_id=USER_ID, total_date=date(2026, 8, 25))
    await repo.upsert(total)
    handler = GetCurrentDailyTotalHandler(repo, cache=cache)

    await handler.handle(GetCurrentDailyTotalQuery(user_id=USER_ID, total_date=date(2026, 8, 25)))

    assert cache.set_calls == 1
