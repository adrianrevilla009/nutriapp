"""RabbitMqEventPublisher -- implements EventPublisherPort.

Naming convention (messaging-conventions SKILL.md): the producing-service
segment uses the *short* name (`-service`/`-svc` suffix dropped), matching
identity-service's already-running `identity.events` /
`identity.user.<event_type>` pattern -- `profile.events` exchange,
`profile.profile.<event_type_snake_case>` routing key.
"""

from __future__ import annotations

import json
import re

import aio_pika

from domain.events.base import DomainEvent

EXCHANGE_NAME = "profile.events"

_CAMEL_TO_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")


def routing_key_for(event_type: str) -> str:
    snake_case = _CAMEL_TO_SNAKE_RE.sub("_", event_type).lower()
    return f"profile.profile.{snake_case}"


class RabbitMqEventPublisher:
    """Implements domain.ports.event_publisher_port.EventPublisherPort."""

    def __init__(self, exchange: aio_pika.abc.AbstractExchange) -> None:
        self._exchange = exchange

    @classmethod
    async def create(
        cls, connection: aio_pika.abc.AbstractRobustConnection
    ) -> RabbitMqEventPublisher:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        return cls(exchange)

    async def publish(self, event: DomainEvent) -> None:
        body = json.dumps(event.to_wire()).encode("utf-8")
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            message_id=str(event.event_id),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=routing_key_for(event.event_type))
