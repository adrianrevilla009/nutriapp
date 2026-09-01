"""EntitlementCacheRepositoryPort -- the local, event-projected read cache
of `billing-service`'s entitlement state (implementation plan section
1.2). `get()` returns `None` on a genuine cache miss (no row for that
user yet -- a lagging/not-yet-processed consumer), distinct from an
explicit `False` (not entitled) or `True` (entitled) row -- callers
(`application/entitlement_check.py`'s `is_user_entitled`) fall back to
`EntitlementCheckPort` only on `None`, per the plan's cache-first design.
Mirrors `recipe-service`'s port of the same name exactly."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol


class EntitlementCacheRepositoryPort(Protocol):
    async def get(self, user_id: uuid.UUID) -> bool | None: ...

    async def upsert(self, user_id: uuid.UUID, entitled: bool, updated_at: datetime) -> None: ...
