"""The one entitlement-gating check `GetReportHandler`/`ExportReportHandler`
funnel through -- reports/exports are Pro-gated (implementation plan
section 1 acceptance criterion 4), `GetWeeklyTrendHandler` is NOT gated
and never calls this at all.

Strategy: cache-first, falling back to the synchronous
`EntitlementCheckPort` ONLY on a genuine cache miss
(`entitlement_cache.get()` returns `None`, not `False`). The fallback
result is deliberately never written back into the cache -- this function
holds no reference to any write method on `EntitlementCacheRepositoryPort`
at all, the same structural guarantee recipe-service's/social-service's
identical helper provides (test-plan section 2's explicit assertion).

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
