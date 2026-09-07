"""OutboxRepositoryPort -- scaffolded for architectural symmetry, same
unused-this-pass status as EventPublisherPort (implementation plan
section 5)."""

from __future__ import annotations

import uuid
from typing import Any, Protocol


class OutboxRepositoryPort(Protocol):
    async def enqueue(self, event: dict[str, Any]) -> None: ...

    async def fetch_unpublished(self, limit: int = 50) -> list[dict[str, Any]]: ...

    async def mark_published(self, event_id: uuid.UUID) -> None: ...
