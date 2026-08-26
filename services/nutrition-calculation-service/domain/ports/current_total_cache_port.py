"""CurrentTotalCachePort -- cache-aside for the current daily nutrient
total read path (caching-strategy SKILL.md). Key namespace
`nutrition:daily-total:*`, 5 min TTL -- new namespace added to
caching-strategy SKILL.md in this PR (implementation plan section 7).
Invalidated event-driven on `NutritionValueRecomputed`, TTL as a safety
net.

Caches the computed `NutrientTotalLine` (the day's aggregated total),
never the full `DailyNutritionTotal` entity's per-entry breakdown (not
needed by any read path) and never an application-layer DTO (ADR-0001)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from domain.value_objects.nutrient_total_line import NutrientTotalLine

CURRENT_TOTAL_CACHE_TTL_SECONDS = 300


class CurrentTotalCachePort(Protocol):
    async def get(self, user_id: uuid.UUID, total_date: date) -> NutrientTotalLine | None: ...

    async def set(self, user_id: uuid.UUID, total_date: date, line: NutrientTotalLine) -> None: ...

    async def invalidate(self, user_id: uuid.UUID, total_date: date) -> None: ...
