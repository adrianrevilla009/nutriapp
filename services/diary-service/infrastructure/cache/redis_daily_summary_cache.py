"""RedisDailySummaryCache -- implements DailySummaryCachePort.

Cache-aside for daily_summary_view, the "hot aggregate" (implementation
plan section 7, caching-strategy SKILL.md). Key namespace:
diary:{user_id}:summary:{date}. TTL: 60s. Invalidation is event-driven:
diary_event_projector_consumer calls invalidate() for the (user_id, date)
PostgresDailySummaryProjector.apply() reports as touched, immediately
after updating Postgres -- not left to TTL expiry alone.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

import redis.exceptions
from redis.asyncio import Redis

from domain.ports.daily_summary_cache_port import DAILY_SUMMARY_CACHE_TTL_SECONDS


def _key(user_id: uuid.UUID, summary_date: date) -> str:
    return f"diary:{user_id}:summary:{summary_date.isoformat()}"


class RedisDailySummaryCache:
    """Implements domain.ports.daily_summary_cache_port.DailySummaryCachePort.

    Fails open on a Redis error (unlike identity-service's rate limiter,
    which fails closed): a cache-layer outage should degrade to "always
    read from Postgres," not make the summary endpoint unavailable --
    caching-strategy SKILL.md's default posture for a read-through cache
    that isn't itself a security control.
    """

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def get(self, user_id: uuid.UUID, summary_date: date) -> dict[str, Any] | None:
        try:
            raw = await self._redis.get(_key(user_id, summary_date))
        except redis.exceptions.RedisError:
            return None
        if raw is None:
            return None
        loaded: dict[str, Any] = json.loads(raw)
        return loaded

    async def set(self, user_id: uuid.UUID, summary_date: date, summary: dict[str, Any]) -> None:
        try:
            await self._redis.set(
                _key(user_id, summary_date),
                json.dumps(summary),
                ex=DAILY_SUMMARY_CACHE_TTL_SECONDS,
            )
        except redis.exceptions.RedisError:
            pass

    async def invalidate(self, user_id: uuid.UUID, summary_date: date) -> None:
        try:
            await self._redis.delete(_key(user_id, summary_date))
        except redis.exceptions.RedisError:
            pass
