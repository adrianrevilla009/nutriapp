from __future__ import annotations

from typing import Protocol


class RateLimiterUnavailableError(Exception):
    """Raised when the rate limiter's backing store is unreachable.

    The application layer maps this to HTTP 503 on register/login/
    password-reset-request — the limiter fails closed (implementation
    plan section 7), never open.
    """


class RateLimitExceededError(Exception):
    """Raised when the caller has exceeded the configured threshold."""


class RateLimiterPort(Protocol):
    async def check_and_increment(self, key: str, limit: int, window_seconds: int) -> None:
        """Raises RateLimitExceededError if over threshold, or
        RateLimiterUnavailableError if the backing store can't be reached."""
        ...
