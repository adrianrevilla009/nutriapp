from __future__ import annotations

import uuid
from dataclasses import dataclass

from application.dto.nutrition_target_dto import NutritionTargetDTO
from domain.ports.target_history_repository_port import TargetHistoryRepositoryPort


@dataclass(frozen=True, slots=True)
class GetTargetHistoryQuery:
    user_id: uuid.UUID


class GetTargetHistoryHandler:
    def __init__(self, history_repository: TargetHistoryRepositoryPort) -> None:
        self._history_repository = history_repository

    async def handle(self, query: GetTargetHistoryQuery) -> list[NutritionTargetDTO]:
        history = await self._history_repository.list_history(query.user_id)
        return [NutritionTargetDTO.from_entity(target) for target in history]
