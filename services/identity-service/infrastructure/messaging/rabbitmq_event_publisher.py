"""RabbitMqEventPublisher — implements EventPublisherPort.

Naming convention (messaging-conventions SKILL.md):
`{producing_service}.{aggregate}.{event_type_snake_case}`, published to a
topic exchange per producing service (`identity.events`).
"""

from __future__ import annotations

import json

import aio_pika

from domain.events.base import DomainEvent

EXCHANGE_NAME = "identity.events"

_ROUTING_KEYS: dict[str, str] = {
    "UserRegistered": "identity.user.registered",
    "PasswordResetRequested": "identity.user.password_reset_requested",
    "NewDeviceLoginDetected": "identity.user.new_device_login_detected",
}


def routing_key_for(event_type: str) -> str:
    return _ROUTING_KEYS.get(event_type, f"identity.user.{event_type.lower()}")


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
