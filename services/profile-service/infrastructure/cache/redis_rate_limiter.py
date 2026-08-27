"""RedisRateLimiter -- implements RateLimiterPort.

Fixed-window counter via INCR+EXPIRE, mirroring identity-service's adapter
of the same name (implementation plan Addendum 2, requirement 4). Fails
**closed**: any Redis error (connection refused, timeout, etc.) is
surfaced as RateLimiterUnavailableError, which the reveal-metrics handler
maps to 503 -- a deliberate availability/security trade-off (this
endpoint discloses Article 9 health data; an unreachable rate limiter
must never be treated as "no limit").

Key namespace: `profile:ratelimit:reveal-metrics:{caller_hash}:{user_id}`
(see application/queries/get_biometric_snapshot_for_calculation.py),
TTL = the caller-supplied window.
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
