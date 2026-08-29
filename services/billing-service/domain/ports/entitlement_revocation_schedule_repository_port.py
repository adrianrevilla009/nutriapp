"""EntitlementRevocationScheduleRepositoryPort -- the deferred-
`EntitlementRevoked` mechanism (implementation plan section 1.5):
`customer.subscription.deleted` schedules a revocation for
`current_period_end` instead of publishing `EntitlementRevoked`
synchronously; `revocation_scan_worker` polls this repository for due,
unprocessed rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RevocationScheduleEntry:
    user_id: uuid.UUID
    revoke_at: datetime
    processed: bool


class EntitlementRevocationScheduleRepositoryPort(Protocol):
    async def upsert_pending(self, user_id: uuid.UUID, revoke_at: datetime) -> None:
        """Creates a new pending row, or confirms/updates the existing
        pending row's `revoke_at` for this user -- idempotent: a replayed
        `customer.subscription.deleted` for the same user must not create
        a second row nor un-process an already-processed one."""
        ...

    async def list_due(self, now: datetime, limit: int = 100) -> list[RevocationScheduleEntry]:
        """Unprocessed rows whose `revoke_at <= now`."""
        ...

    async def mark_processed(self, user_id: uuid.UUID) -> None: ...
