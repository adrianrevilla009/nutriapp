"""UsdaFdcCircuitBreaker — purgatory-based circuit breaker instance,
USDA-specific config (implementation plan section 7): fail_max=5
consecutive failures, reset_timeout=60s (half-open trial after 1 minute).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import purgatory
from purgatory.domain.model import OpenedState

from application.jobs.run_usda_fdc_ingestion import UsdaFdcCircuitOpenError

CIRCUIT_NAME = "usda_fdc"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 60

T = TypeVar("T")


class UsdaFdcCircuitBreaker:
    def __init__(
        self,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: int = DEFAULT_RESET_TIMEOUT_SECONDS,
    ) -> None:
        self._factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )

    async def call(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        breaker = await self._factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                return await func(*args, **kwargs)
        except OpenedState as exc:
            raise UsdaFdcCircuitOpenError("USDA FDC circuit breaker is open.") from exc
