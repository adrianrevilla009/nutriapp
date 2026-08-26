from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol


class DailySummaryReadPort(Protocol):
    async def get_summary(
        self, user_id: uuid.UUID, summary_date: date
    ) -> dict[str, Any] | None: ...
