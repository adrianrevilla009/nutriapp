"""EventPublisherPort -- the outbound-messaging boundary consumed by the
Outbox relay worker (messaging-conventions SKILL.md). Mirrors every other
service's identical port."""

from __future__ import annotations

from typing import Protocol

from domain.events.base import DomainEvent


class EventPublisherPort(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
