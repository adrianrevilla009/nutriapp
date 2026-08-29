"""ReminderScheduleRepositoryPort -- Postgres adapter:
postgres_reminder_schedule_repository.py."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from domain.entities.reminder_schedule_entry import ReminderScheduleEntry
from domain.value_objects.reminder_status import ReminderStatus


class ReminderScheduleRepositoryPort(Protocol):
    async def upsert(self, entry: ReminderScheduleEntry) -> None: ...

    async def get_by_source(
        self, source_aggregate_id: str, category_name: str
    ) -> ReminderScheduleEntry | None: ...

    async def remove_by_source(self, source_aggregate_id: str, category_name: str) -> None: ...

    async def list_pending(self, now: datetime) -> list[ReminderScheduleEntry]: ...

    async def mark_status(
        self,
        schedule_id: uuid.UUID,
        status: ReminderStatus,
        next_eligible_check_at: datetime | None = None,
    ) -> None: ...
