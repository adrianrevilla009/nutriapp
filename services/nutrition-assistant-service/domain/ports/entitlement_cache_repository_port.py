"""EntitlementCacheRepositoryPort -- structurally identical to
recipe-service's/social-service's/analytics-service's port of the same
name. `get` returns None on a genuine cache miss (distinct from a cached
`False`) so application/entitlement_check.py can tell "never checked" from
"checked and not entitled" apart."""

from __future__ import annotations

import uuid
from typing import Protocol


class EntitlementCacheRepositoryPort(Protocol):
    async def get(self, user_id: uuid.UUID) -> bool | None: ...

    async def set(self, user_id: uuid.UUID, entitled: bool) -> None: ...
