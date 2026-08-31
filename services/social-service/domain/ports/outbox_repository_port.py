"""OutboxRepositoryPort -- mirrors every other event-driven-CRUD service's
identical port shape (messaging-conventions SKILL.md's Outbox Pattern is a
repo-wide convention)."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.events.base import DomainEvent


class OutboxRepositoryPort(Protocol):
    async def enqueue(self, event: DomainEvent) -> None: ...

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]: ...

    async def mark_published(self, event_id: uuid.UUID) -> None: ...
