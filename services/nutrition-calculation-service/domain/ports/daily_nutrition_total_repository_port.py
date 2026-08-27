"""DailyNutritionTotalRepositoryPort.

`find_date_for_entry` exists to resolve `FoodEntryDeleted`'s payload
(`{entry_id, user_id, deleted_at}`, per docs/events-catalog.md) to the
`total_date` its contribution was originally recorded under -- that event
carries no date itself, unlike `FoodEntryLogged`/`FoodEntryCorrected`'s
`occurred_at`. Returns `None` if no day has a recorded contribution for
that `entry_id` (e.g. a replayed delete for an already-removed entry, or
an entry this service never saw logged) -- the consumer treats that as a
safe, idempotent no-op rather than an error.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from domain.entities.daily_nutrition_total import DailyNutritionTotal


class DailyNutritionTotalRepositoryPort(Protocol):
    async def get(self, user_id: uuid.UUID, total_date: date) -> DailyNutritionTotal | None: ...

    async def upsert(self, total: DailyNutritionTotal) -> None: ...

    async def find_date_for_entry(self, user_id: uuid.UUID, entry_id: uuid.UUID) -> date | None: ...
