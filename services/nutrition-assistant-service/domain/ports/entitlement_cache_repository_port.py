"""EntitlementCacheRepositoryPort -- structurally identical to
recipe-service's/social-service's/analytics-service's port of the same
name. `get` returns None on a genuine cache miss (distinct from a cached
`False`) so application/entitlement_check.py can tell "never checked" from
"checked and not entitled" apart.

`upsert` (implementation plan addendum, 2026-09-08) takes the event's own
`occurred_at` (`granted_at`/`revoked_at`), not the cache-write wall-clock
time, matching analytics-service's `upsert` signature exactly -- the
event's own timestamp is real information worth preserving for audit/
debugging (when did billing-service actually grant/revoke, vs. when did
this service's cache happen to catch up). Nothing in this codebase calls
a narrower `set()` any more; `application/entitlement_check.py`'s
synchronous-fallback path still never calls `upsert` at all -- see that
module's docstring and CLAUDE.md's "Never do this" section."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol


class EntitlementCacheRepositoryPort(Protocol):
    async def get(self, user_id: uuid.UUID) -> bool | None: ...

    async def upsert(self, user_id: uuid.UUID, entitled: bool, occurred_at: datetime) -> None: ...
