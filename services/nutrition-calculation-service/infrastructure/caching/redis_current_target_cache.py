"""RedisCurrentTargetCache -- implements CurrentTargetCachePort.

Cache-aside for the current nutrition target (caching-strategy SKILL.md).
Key namespace: `nutrition:current-target:{user_id}`. TTL: 1h
(implementation plan section 7). Invalidation is event-driven: the
recompute command's caller (RabbitMqProfileMetricsConsumer) calls
invalidate() immediately after a successful recompute, not left to TTL
expiry alone.

Fails open on a Redis error (same posture as diary-service's
RedisDailySummaryCache): a cache-layer outage degrades to "always read
from Postgres," never makes the target endpoint unavailable.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import redis.exceptions
from redis.asyncio import Redis

from domain.entities.nutrition_target import NutritionTarget
from domain.ports.current_target_cache_port import CURRENT_TARGET_CACHE_TTL_SECONDS
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant


def _key(user_id: uuid.UUID) -> str:
    return f"nutrition:current-target:{user_id}"


def _serialize(target: NutritionTarget) -> str:
    return json.dumps(
        {
            "user_id": str(target.user_id),
            "bmr_kcal": target.bmr_kcal,
            "tdee_kcal": target.tdee_kcal,
            "calorie_target_kcal": target.calorie_target_kcal,
            "protein_g_min": target.macro_targets.protein_g_min,
            "protein_g_max": target.macro_targets.protein_g_max,
            "fat_g_min": target.macro_targets.fat_g_min,
            "carbs_g": target.macro_targets.carbs_g,
            "carbs_floored": target.macro_targets.carbs_floored,
            "goal_type": target.goal_type.value,
            "activity_level": target.activity_level.value,
            "sex_constant_used": target.sex_constant_used.value,
            "clamped": target.clamped,
            "clamp_reason": target.clamp_reason,
            "formula_version": target.formula_version,
            "reason": target.reason,
            "effective_from": target.effective_from.isoformat(),
        }
    )


def _deserialize(raw: str) -> NutritionTarget:
    data = json.loads(raw)
    return NutritionTarget(
        user_id=uuid.UUID(data["user_id"]),
        bmr_kcal=data["bmr_kcal"],
        tdee_kcal=data["tdee_kcal"],
        calorie_target_kcal=data["calorie_target_kcal"],
        macro_targets=MacroTargetRange(
            protein_g_min=data["protein_g_min"],
            protein_g_max=data["protein_g_max"],
            fat_g_min=data["fat_g_min"],
            carbs_g=data["carbs_g"],
            carbs_floored=data["carbs_floored"],
        ),
        goal_type=GoalType(data["goal_type"]),
        activity_level=ActivityLevel(data["activity_level"]),
        sex_constant_used=CalculationSexConstant(data["sex_constant_used"]),
        clamped=data["clamped"],
        clamp_reason=data["clamp_reason"],
        formula_version=data["formula_version"],
        reason=data["reason"],
        effective_from=datetime.fromisoformat(data["effective_from"]),
    )


class RedisCurrentTargetCache:
    """Implements domain.ports.current_target_cache_port.CurrentTargetCachePort."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def get(self, user_id: uuid.UUID) -> NutritionTarget | None:
        try:
            raw = await self._redis.get(_key(user_id))
        except redis.exceptions.RedisError:
            return None
        if raw is None:
            return None
        raw_str = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return _deserialize(raw_str)

    async def set(self, user_id: uuid.UUID, target: NutritionTarget) -> None:
        try:
            await self._redis.set(
                _key(user_id), _serialize(target), ex=CURRENT_TARGET_CACHE_TTL_SECONDS
            )
        except redis.exceptions.RedisError:
            pass

    async def invalidate(self, user_id: uuid.UUID) -> None:
        try:
            await self._redis.delete(_key(user_id))
        except redis.exceptions.RedisError:
            pass
