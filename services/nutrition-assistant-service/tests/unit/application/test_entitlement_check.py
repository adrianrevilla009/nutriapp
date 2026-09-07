from __future__ import annotations

import uuid

from application.entitlement_check import is_user_entitled
from tests.fixtures.fakes import FakeEntitlementCacheRepository, FakeEntitlementCheckPort


async def test_cache_hit_true_skips_fallback() -> None:
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository(cached={user_id: True})
    check = FakeEntitlementCheckPort(result=False)
    assert await is_user_entitled(user_id, cache, check) is True
    assert check.call_count == 0


async def test_cache_hit_false_skips_fallback() -> None:
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository(cached={user_id: False})
    check = FakeEntitlementCheckPort(result=True)
    assert await is_user_entitled(user_id, cache, check) is False
    assert check.call_count == 0


async def test_cache_miss_falls_back_and_never_writes_back() -> None:
    """The single most important structural invariant (recipe-service's/
    social-service's/analytics-service's precedent, restated in the
    persisted test plan section 2)."""
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository()
    check = FakeEntitlementCheckPort(result=True)
    result = await is_user_entitled(user_id, cache, check)
    assert result is True
    assert check.call_count == 1
    assert cache.set_calls == []  # NEVER written back


async def test_fallback_unavailable_fails_safe_not_entitled() -> None:
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository()
    check = FakeEntitlementCheckPort(raise_unavailable=True)
    result = await is_user_entitled(user_id, cache, check)
    assert result is False
    assert cache.set_calls == []
