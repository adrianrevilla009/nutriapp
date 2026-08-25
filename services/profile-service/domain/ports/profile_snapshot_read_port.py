from __future__ import annotations

import uuid
from typing import Any, Protocol


class ProfileSnapshotReadPort(Protocol):
    async def get_snapshot(self, user_id: uuid.UUID) -> dict[str, Any] | None: ...
