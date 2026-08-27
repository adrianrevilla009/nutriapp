from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from application.dto.nutrient_total_dto import NutrientTotalDTO
from application.errors import DailyNutritionTotalNotFoundError
from domain.ports.current_total_cache_port import CurrentTotalCachePort
from domain.ports.daily_nutrition_total_repository_port import DailyNutritionTotalRepositoryPort


@dataclass(frozen=True, slots=True)
class GetCurrentDailyTotalQuery:
    user_id: uuid.UUID
    total_date: date


class GetCurrentDailyTotalHandler:
    def __init__(
        self,
        totals_repository: DailyNutritionTotalRepositoryPort,
        cache: CurrentTotalCachePort | None = None,
    ) -> None:
        self._totals_repository = totals_repository
        self._cache = cache

    async def handle(self, query: GetCurrentDailyTotalQuery) -> NutrientTotalDTO:
        if self._cache is not None:
            cached_line = await self._cache.get(query.user_id, query.total_date)
            if cached_line is not None:
                return NutrientTotalDTO.from_line(
                    user_id=query.user_id, total_date=query.total_date, line=cached_line
                )

        total = await self._totals_repository.get(query.user_id, query.total_date)
        if total is None:
            raise DailyNutritionTotalNotFoundError(
                f"No computed daily total for user {query.user_id} on {query.total_date}."
            )

        dto = NutrientTotalDTO.from_entity(total)
        if self._cache is not None:
            await self._cache.set(query.user_id, query.total_date, total.compute_total())

        return dto
