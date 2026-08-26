"""ListFoodEntriesQuery + handler -- reads the food_entries_view read
model, never replays the event stream on a read."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from application.dto.diary_dto import FoodEntryDTO
from domain.ports.food_entries_read_port import FoodEntriesReadPort


@dataclass(frozen=True, slots=True)
class ListFoodEntriesQuery:
    user_id: uuid.UUID
    from_date: date | None = None
    to_date: date | None = None


class ListFoodEntriesHandler:
    def __init__(self, read_port: FoodEntriesReadPort) -> None:
        self._read_port = read_port

    async def handle(self, query: ListFoodEntriesQuery) -> list[FoodEntryDTO]:
        rows = await self._read_port.list_entries(query.user_id, query.from_date, query.to_date)
        return [
            FoodEntryDTO(
                entry_id=row["entry_id"],
                user_id=row["user_id"],
                source=row["source"],
                meal_slot=row["meal_slot"],
                occurred_at=row["occurred_at"],
                deleted=row["deleted"],
            )
            for row in rows
        ]
