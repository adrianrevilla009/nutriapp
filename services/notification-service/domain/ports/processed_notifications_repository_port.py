"""ProcessedNotificationsRepositoryPort -- idempotency dedup on
(event_id, channel) (CLAUDE.md section 2.4 / notification-agent.md).
Postgres adapter: postgres_processed_notifications_repository.py."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedNotificationsRepositoryPort(Protocol):
    async def already_processed(self, event_id: uuid.UUID, channel: str) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID, channel: str) -> None: ...
