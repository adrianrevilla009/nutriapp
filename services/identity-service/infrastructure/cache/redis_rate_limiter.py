"""RedisRateLimiter — implements RateLimiterPort.

Fixed-window counter via INCR+EXPIRE. Fails **closed**: any Redis error
(connection refused, timeout, etc.) is surfaced as
RateLimiterUnavailableError, which the HTTP layer maps to 503 on
register/login/password-reset-request — a deliberate availability/
security trade-off (implementation plan section 7), confirmed over the
"fail open" alternative.

Key namespace: `identity:ratelimit:{endpoint}:{ip_or_user}`, TTL = 60s
(caching-strategy SKILL.md TTL table).
"""
from __future__ import annotations

import redis.exceptions
from redis.asyncio import Redis

from domain.ports.rate_limiter_port import RateLimiterUnavailableError, RateLimitExceededError


class RedisRateLimiter:
    """Implements domain.ports.rate_limiter_port.RateLimiterPort."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def check_and_increment(self, key: str, limit: int, window_seconds: int) -> None:
        try:
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, window_seconds)
        except redis.exceptions.RedisError as exc:
            raise RateLimiterUnavailableError(
                "Rate limiter backing store is unreachable; failing closed."
            ) from exc

        if current > limit:
            raise RateLimitExceededError(f"Rate limit exceeded for key '{key}'.")
