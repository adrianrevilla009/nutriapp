from __future__ import annotations

import uuid
from dataclasses import dataclass

from application.dto.nutrition_target_dto import NutritionTargetDTO
from application.errors import NutritionTargetNotFoundError
from domain.ports.current_target_cache_port import CurrentTargetCachePort
from domain.ports.nutrition_target_repository_port import NutritionTargetRepositoryPort


@dataclass(frozen=True, slots=True)
class GetCurrentNutritionTargetQuery:
    user_id: uuid.UUID


class GetCurrentNutritionTargetHandler:
    def __init__(
        self,
        target_repository: NutritionTargetRepositoryPort,
        cache: CurrentTargetCachePort | None = None,
    ) -> None:
        self._target_repository = target_repository
        self._cache = cache

    async def handle(self, query: GetCurrentNutritionTargetQuery) -> NutritionTargetDTO:
        if self._cache is not None:
            cached = await self._cache.get(query.user_id)
            if cached is not None:
                return NutritionTargetDTO.from_entity(cached)

        target = await self._target_repository.get_current(query.user_id)
        if target is None:
            raise NutritionTargetNotFoundError(
                f"No computed nutrition target yet for user {query.user_id}."
            )

        if self._cache is not None:
            await self._cache.set(query.user_id, target)

        return NutritionTargetDTO.from_entity(target)
