"""NutritionHistoryRepositoryPort -- structured projection of
nutrition-calculation-service's NutritionValueRecomputed/NutritionTargetUpdated
events, keyed by user_id. Concrete adapter:
infrastructure.persistence.postgres_nutrition_history_repository.PostgresNutritionHistoryRepository."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from domain.value_objects.retrieved_record import RetrievedRecord


class NutritionHistoryRepositoryPort(Protocol):
    async def upsert_value_recomputed(
        self,
        user_id: uuid.UUID,
        scope: str,
        reference_id: str,
        on_date: date | None,
        summary: str,
    ) -> None: ...

    async def upsert_target_updated(self, user_id: uuid.UUID, summary: str) -> None: ...

    async def recent_for_user(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> list[RetrievedRecord]: ...
