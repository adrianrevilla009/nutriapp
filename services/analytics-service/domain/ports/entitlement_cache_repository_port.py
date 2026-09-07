"""EntitlementCacheRepositoryPort -- structurally identical to
`recipe-service`'s/`social-service`'s own port of the same name (CLAUDE.md
section 2.5: own local copy, never imported cross-service). `get()`
returns `None` for a genuine cache-miss, distinguishable from a cached
`False`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol


class EntitlementCacheRepositoryPort(Protocol):
    async def get(self, user_id: uuid.UUID) -> bool | None: ...

    async def upsert(self, user_id: uuid.UUID, entitled: bool, updated_at: datetime) -> None: ...
