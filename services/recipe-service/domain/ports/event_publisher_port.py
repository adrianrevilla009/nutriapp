"""EventPublisherPort -- the outbound-broker publishing boundary consumed
by `OutboxRelayWorker`. Concrete adapter:
`infrastructure.messaging.rabbitmq_event_publisher.RabbitMqEventPublisher`.
"""

from __future__ import annotations

from typing import Protocol

from domain.events.base import DomainEvent


class EventPublisherPort(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
