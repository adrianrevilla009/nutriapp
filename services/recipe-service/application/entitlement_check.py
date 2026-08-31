"""Shared entitlement-check helper -- used by `PublishRecipeHandler` and
`SearchPublishedRecipesHandler` (implementation plan section 1.7):
cache-first, falling back to the synchronous `EntitlementCheckPort` ONLY
on a genuine cache miss (`entitlement_cache.get()` returns `None`). The
fallback result is deliberately NEVER written back into the cache -- this
function has no reference to any write method on
`EntitlementCacheRepositoryPort`, which is what makes that a structural
guarantee rather than a discipline someone could forget (test-plan
section 1's explicit assertion).

A fallback-check failure (circuit open, timeout) fails SAFE -- treated as
not entitled, never fail open (saga-conventions SKILL.md, ADR-0015).
"""

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
    cached = await entitlement_cache.get(user_id)
    if cached is not None:
        return cached

    try:
        return await entitlement_check.check_entitlement(user_id)
    except EntitlementCheckUnavailableError:
        return False
