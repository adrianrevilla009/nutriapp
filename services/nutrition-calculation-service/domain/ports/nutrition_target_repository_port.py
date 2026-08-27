from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.nutrition_target import NutritionTarget


class NutritionTargetRepositoryPort(Protocol):
    async def get_current(self, user_id: uuid.UUID) -> NutritionTarget | None: ...

    async def upsert(self, target: NutritionTarget) -> None: ...
