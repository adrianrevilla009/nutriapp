"""PendingPushDispatchRepositoryPort -- Postgres adapter:
postgres_pending_push_dispatch_repository.py."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from domain.entities.pending_push_dispatch import PendingPushDispatch
from domain.value_objects.pending_dispatch_status import PendingDispatchStatus


class PendingPushDispatchRepositoryPort(Protocol):
    async def add(self, dispatch: PendingPushDispatch) -> None: ...

    async def list_due(self, now: datetime) -> list[PendingPushDispatch]: ...

    async def mark_status(
        self,
        dispatch_id: uuid.UUID,
        status: PendingDispatchStatus,
        earliest_dispatch_at: datetime | None = None,
    ) -> None: ...
