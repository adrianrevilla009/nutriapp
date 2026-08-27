from __future__ import annotations

import uuid
from typing import Protocol

from domain.events.base import DomainEvent


class OutboxRepositoryPort(Protocol):
    async def enqueue(self, event: DomainEvent) -> None: ...

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]: ...

    async def mark_published(self, event_id: uuid.UUID) -> None: ...
