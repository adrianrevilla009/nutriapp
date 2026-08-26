"""5 consecutive failures trips the breaker; a subsequent call within
reset_timeout short-circuits without attempting a network call; a call
after reset_timeout half-opens and, on success, closes the breaker again
(test-plan section 2, purgatory-backed per implementation plan section 7).
"""

from __future__ import annotations

import asyncio

import pytest

from application.jobs.run_usda_fdc_ingestion import UsdaFdcCircuitOpenError
from infrastructure.external.usda_fdc.circuit_breaker import UsdaFdcCircuitBreaker


async def test_five_consecutive_failures_trips_breaker():
    breaker = UsdaFdcCircuitBreaker(fail_max=5, reset_timeout_seconds=60)

    async def always_fails():
        raise RuntimeError("boom")

    for _ in range(5):
        with pytest.raises(RuntimeError):
            await breaker.call(always_fails)

    calls = 0

    async def should_not_be_called():
        nonlocal calls
        calls += 1
        return "unreachable"

    with pytest.raises(UsdaFdcCircuitOpenError):
        await breaker.call(should_not_be_called)
    assert calls == 0


async def test_breaker_half_opens_and_closes_after_reset_timeout():
    breaker = UsdaFdcCircuitBreaker(fail_max=2, reset_timeout_seconds=0.05)

    async def always_fails():
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(always_fails)

    with pytest.raises(UsdaFdcCircuitOpenError):
        await breaker.call(always_fails)

    await asyncio.sleep(0.1)  # past reset_timeout_seconds

    async def succeeds():
        return "ok"

    result = await breaker.call(succeeds)
    assert result == "ok"

    # Breaker is closed again — a subsequent call goes through normally.
    result_2 = await breaker.call(succeeds)
    assert result_2 == "ok"
