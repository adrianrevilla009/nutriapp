"""GetMealPlanCalendarQuery + handler -- reads the meal_plan_view read
model, never replays the event stream on a read."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from application.dto.diary_dto import MealPlanEntryDTO
from domain.ports.meal_plan_read_port import MealPlanReadPort


@dataclass(frozen=True, slots=True)
class GetMealPlanCalendarQuery:
    user_id: uuid.UUID
    from_date: date
    to_date: date


class GetMealPlanCalendarHandler:
    def __init__(self, read_port: MealPlanReadPort) -> None:
        self._read_port = read_port

    async def handle(self, query: GetMealPlanCalendarQuery) -> list[MealPlanEntryDTO]:
        rows = await self._read_port.get_calendar(query.user_id, query.from_date, query.to_date)
        return [
            MealPlanEntryDTO(
                plan_entry_id=row["plan_entry_id"],
                user_id=row["user_id"],
                source=row["source"],
                meal_slot=row["meal_slot"],
                planned_for=row["planned_for"],
                removed=row["removed"],
            )
            for row in rows
        ]
