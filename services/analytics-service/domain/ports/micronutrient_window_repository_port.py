"""MicronutrientWindowRepositoryPort -- backs `HandleNutritionValueRecomputedHandler`'s
upsert and `HandleNutritionTargetUpdatedHandler`'s current-target lookup.
Historical rows are immutable once written (a later `NutritionTargetUpdated`
never rewrites an already-recorded day's `target_min` -- test-plan section
2's explicit assertion)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from domain.value_objects.trend_point import TrendPoint


class MicronutrientWindowRepositoryPort(Protocol):
    async def upsert(
        self,
        user_id: uuid.UUID,
        nutrient: str,
        on_date: date,
        value: float,
        target_min: float | None,
    ) -> None: ...

    async def list_recent(
        self, user_id: uuid.UUID, nutrient: str, limit_days: int
    ) -> list[TrendPoint]: ...

    async def get_current_target_min(self, user_id: uuid.UUID, nutrient: str) -> float | None: ...

    async def set_current_target_min(
        self, user_id: uuid.UUID, nutrient: str, target_min: float | None
    ) -> None: ...

    async def list_window(
        self, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[dict[str, object]]: ...
