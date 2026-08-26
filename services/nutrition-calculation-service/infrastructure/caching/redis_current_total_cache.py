"""RedisCurrentTotalCache -- implements CurrentTotalCachePort.

Cache-aside for the current daily nutrient total (caching-strategy
SKILL.md). Key namespace: `nutrition:daily-total:{user_id}:{date}` -- new
namespace, added to `.claude/skills/caching-strategy/SKILL.md` in this PR
(implementation plan section 7). TTL: 5 minutes. Invalidation is
event-driven: the recompute command's caller
(RabbitMqDiaryFoodEntryConsumer) calls invalidate() immediately after a
successful recompute.

Fails open on a Redis error, same posture as RedisCurrentTargetCache.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

import redis.exceptions
from redis.asyncio import Redis

from domain.ports.current_total_cache_port import CURRENT_TOTAL_CACHE_TTL_SECONDS
from domain.value_objects.nutrient_total_line import NutrientTotalLine
from infrastructure.persistence.mappers import (
    nutrient_total_line_from_dict,
    nutrient_total_line_to_dict,
)


def _key(user_id: uuid.UUID, total_date: date) -> str:
    return f"nutrition:daily-total:{user_id}:{total_date.isoformat()}"


class RedisCurrentTotalCache:
    """Implements domain.ports.current_total_cache_port.CurrentTotalCachePort."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def get(self, user_id: uuid.UUID, total_date: date) -> NutrientTotalLine | None:
        try:
            raw = await self._redis.get(_key(user_id, total_date))
        except redis.exceptions.RedisError:
            return None
        if raw is None:
            return None
        return nutrient_total_line_from_dict(json.loads(raw))

    async def set(self, user_id: uuid.UUID, total_date: date, line: NutrientTotalLine) -> None:
        try:
            await self._redis.set(
                _key(user_id, total_date),
                json.dumps(nutrient_total_line_to_dict(line)),
                ex=CURRENT_TOTAL_CACHE_TTL_SECONDS,
            )
        except redis.exceptions.RedisError:
            pass

    async def invalidate(self, user_id: uuid.UUID, total_date: date) -> None:
        try:
            await self._redis.delete(_key(user_id, total_date))
        except redis.exceptions.RedisError:
            pass
