from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol


class WaterIntakeReadPort(Protocol):
    async def list_intake(
        self, user_id: uuid.UUID, from_date: date | None, to_date: date | None
    ) -> list[dict[str, Any]]: ...
