"""RateLimiterPort -- mirrors identity-service's port of the same name
(implementation plan Addendum 2, requirement 4: "reuse identity-service's
RateLimiterPort/RedisRateLimiter pattern"). Not literally shared code
(each service owns its own adapters, CLAUDE.md section 2.5's "no shared
schemas/state across service boundaries" principle applied to internal
libraries too), but the exact same contract and fail-closed semantics.
"""

from __future__ import annotations

from typing import Protocol


class RateLimiterUnavailableError(Exception):
    """Raised when the rate limiter's backing store is unreachable. The
    limiter fails **closed**, never open -- see infrastructure/cache/
    redis_rate_limiter.py."""


class RateLimitExceededError(Exception):
    """Raised when the caller has exceeded the configured threshold."""


class RateLimiterPort(Protocol):
    async def check_and_increment(self, key: str, limit: int, window_seconds: int) -> None:
        """Raises RateLimitExceededError if over threshold, or
        RateLimiterUnavailableError if the backing store can't be reached."""
        ...
