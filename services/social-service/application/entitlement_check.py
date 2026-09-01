"""The one entitlement-gating check `FollowUserHandler`, `UnfollowUserHandler`,
and `GetFeedHandler` all funnel through (implementation plan section
1.2) -- connecting with other users and viewing the feed are both
Pro-gated (social-agent.md's bounded-context rule).

Strategy: cache-first, falling back to the synchronous
`EntitlementCheckPort` ONLY on a genuine cache miss
(`entitlement_cache.get()` returns `None`, not `False`). The fallback
result is deliberately never written back into the cache -- this
function holds no reference to any write method on
`EntitlementCacheRepositoryPort` at all, which makes "never write the
fallback back" a structural guarantee rather than a discipline someone
could forget (test-plan section 1's explicit assertion).

A fallback-check failure (circuit open, timeout, credential rejected)
fails SAFE -- treated as not entitled, never fail open (saga-conventions
SKILL.md, ADR-0015)."""

from __future__ import annotations

import uuid

from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.entitlement_check_port import (
    EntitlementCheckPort,
    EntitlementCheckUnavailableError,
)


async def is_user_entitled(
    user_id: uuid.UUID,
    entitlement_cache: EntitlementCacheRepositoryPort,
    entitlement_check: EntitlementCheckPort,
) -> bool:
    cached_result = await entitlement_cache.get(user_id)
    if cached_result is not None:
        return cached_result

    try:
        return await entitlement_check.check_entitlement(user_id)
    except EntitlementCheckUnavailableError:
        return False
