from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedEventsPort(Protocol):
    async def already_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
