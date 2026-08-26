from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol


class FoodEntriesReadPort(Protocol):
    async def list_entries(
        self, user_id: uuid.UUID, from_date: date | None, to_date: date | None
    ) -> list[dict[str, Any]]: ...
