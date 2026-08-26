from __future__ import annotations

import uuid
from typing import Any, Protocol


class FastingWindowsReadPort(Protocol):
    async def get_history(self, user_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]: ...
