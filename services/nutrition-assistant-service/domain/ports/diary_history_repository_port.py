"""DiaryHistoryRepositoryPort -- structured projection of diary-service's
FoodEntryLogged/Corrected/Deleted and WaterIntakeLogged/Removed events,
keyed by user_id, incrementally maintained (never a full-history rewrite
per event, per .claude/agents/nutrition-assistant-agent.md). Concrete
adapter: infrastructure.persistence.postgres_diary_history_repository.PostgresDiaryHistoryRepository."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from domain.value_objects.retrieved_record import RetrievedRecord


class DiaryHistoryRepositoryPort(Protocol):
    async def upsert_food_entry(
        self,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        summary: str,
        occurred_at: datetime,
    ) -> None: ...

    async def remove_food_entry(self, entry_id: uuid.UUID) -> None: ...

    async def upsert_water_intake(
        self,
        intake_id: uuid.UUID,
        user_id: uuid.UUID,
        summary: str,
        occurred_at: datetime,
    ) -> None: ...

    async def remove_water_intake(self, intake_id: uuid.UUID) -> None: ...

    async def recent_for_user(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> list[RetrievedRecord]: ...
