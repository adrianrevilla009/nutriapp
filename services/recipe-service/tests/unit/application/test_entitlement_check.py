from __future__ import annotations

import uuid

from application.entitlement_check import is_user_entitled
from tests.fixtures.factories import FakeEntitlementCacheRepository, FakeEntitlementCheckPort


async def test_cache_hit_never_calls_fallback():
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository(seed={user_id: True})
    check = FakeEntitlementCheckPort()

    result = await is_user_entitled(user_id, cache, check)

    assert result is True
    assert check.calls == []


async def test_cache_miss_fallback_unavailable_fails_safe_not_entitled():
    """A fallback-check failure (circuit open, timeout) must fail SAFE --
    treated as not entitled, never fail open (saga-conventions SKILL.md,
    ADR-0015)."""
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository(seed={})
    check = FakeEntitlementCheckPort(raise_unavailable=True)

    result = await is_user_entitled(user_id, cache, check)

    assert result is False
    assert cache.upsert_calls == 0
