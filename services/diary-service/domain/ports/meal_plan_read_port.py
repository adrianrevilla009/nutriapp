from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol


class MealPlanReadPort(Protocol):
    async def get_calendar(
        self, user_id: uuid.UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]: ...
