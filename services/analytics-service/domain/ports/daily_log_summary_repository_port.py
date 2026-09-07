"""DailyLogSummaryRepositoryPort -- backs the five diary-event handlers'
writes and `GetWeeklyTrendHandler`'s bounded, date-ranged reads
(CLAUDE.md's pagination rule: `list_window` always takes an explicit
range, never "fetch everything for this user"). Logged dates for
streak computation are derived from `list_window`'s own rows (a row's
mere existence means that day had at least one logged food/water entry)
-- no separate `list_logged_dates` method is needed.

**Deviation from the persisted implementation plan's table list**
(flagged in the implementation report, not silently absorbed): the plan's
section 3 lists only a single `daily_log_summary` table. Discovered while
implementing this port: `FoodEntryDeleted`'s and `WaterIntakeRemoved`'s
documented payloads (docs/events-catalog.md) carry only an id + timestamp
-- no macro/amount figures -- so reversing a deletion's contribution to a
day's totals is impossible from the deletion event alone. The concrete
Postgres adapter therefore also maintains two small internal per-entry
ledger tables (`food_entry_contributions`, `water_intake_contributions`)
recording what each still-live entry last contributed, purely so
`remove_food_entry`/`remove_water_intake`/`correct_food_entry` can compute
the correct delta. This is an implementation detail of the adapter, not a
port-level concern -- the port below exposes only entry-oriented
operations, never raw deltas, so callers never need to know the ledger
exists."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from domain.services.trend_calculator import DailyMacroTotals


class DailyLogSummaryRepositoryPort(Protocol):
    async def apply_food_entry(
        self,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        on_date: date,
        calories_kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
    ) -> None: ...

    async def correct_food_entry(
        self,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        on_date: date,
        calories_kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
    ) -> None: ...

    async def remove_food_entry(self, entry_id: uuid.UUID) -> None: ...

    async def apply_water_intake(
        self, intake_id: uuid.UUID, user_id: uuid.UUID, on_date: date, amount_ml: float
    ) -> None: ...

    async def remove_water_intake(self, intake_id: uuid.UUID) -> None: ...

    async def list_window(
        self, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DailyMacroTotals]: ...
