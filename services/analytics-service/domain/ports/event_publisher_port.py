"""EventPublisherPort -- the far end of the outbox relay. Own local copy
(CLAUDE.md section 2.5), same shape as every other service's port of the
same name."""

from __future__ import annotations

from typing import Protocol

from domain.events.base import DomainEvent


class EventPublisherPort(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
