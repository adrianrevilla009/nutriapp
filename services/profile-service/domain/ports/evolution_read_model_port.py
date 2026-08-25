from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol


class EvolutionReadModelPort(Protocol):
    async def get_evolution(
        self,
        user_id: uuid.UUID,
        metric: str,
        from_ts: datetime | None,
        to_ts: datetime | None,
    ) -> list[dict[str, Any]]: ...
