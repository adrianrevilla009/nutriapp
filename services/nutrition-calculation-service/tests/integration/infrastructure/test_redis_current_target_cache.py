from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from redis.asyncio import Redis

from domain.entities.nutrition_target import NutritionTarget
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant
from infrastructure.caching.redis_current_target_cache import RedisCurrentTargetCache


@pytest.fixture()
async def redis_client(redis_url):
    client = Redis.from_url(redis_url)
    yield client
    await client.flushall()
    await client.aclose()


def _make_target(user_id: uuid.UUID) -> NutritionTarget:
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
        effective_from=datetime.now(timezone.utc),
    )


async def test_cache_miss_then_hit(redis_client):
    cache = RedisCurrentTargetCache(redis_client)
    user_id = uuid.uuid4()

    assert await cache.get(user_id) is None

    target = _make_target(user_id)
    await cache.set(user_id, target)

    cached = await cache.get(user_id)
    assert cached is not None
    assert cached.calorie_target_kcal == target.calorie_target_kcal
    assert cached.sex_constant_used is CalculationSexConstant.MALE


async def test_invalidate_removes_entry(redis_client):
    cache = RedisCurrentTargetCache(redis_client)
    user_id = uuid.uuid4()
    await cache.set(user_id, _make_target(user_id))

    await cache.invalidate(user_id)

    assert await cache.get(user_id) is None


async def test_connection_failure_fails_open_on_get_set_and_invalidate():
    unreachable_client = Redis(host="127.0.0.1", port=1, socket_connect_timeout=1)
    cache = RedisCurrentTargetCache(unreachable_client)
    user_id = uuid.uuid4()

    assert await cache.get(user_id) is None
    await cache.set(user_id, _make_target(user_id))  # must not raise
    await cache.invalidate(user_id)  # must not raise
    await unreachable_client.aclose()
