from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.nutrition_target import NutritionTarget


class TargetHistoryRepositoryPort(Protocol):
    async def append(self, target: NutritionTarget) -> None: ...

    async def list_history(self, user_id: uuid.UUID) -> list[NutritionTarget]: ...
