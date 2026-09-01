"""RabbitMqEventPublisher -- social-service's `EventPublisherPort` adapter,
the far end of the outbox relay. Publishes to this service's own topic
exchange (`social.events`), one routing key per event type following the
repo-wide `{producing_service}.{aggregate}.{event_type_snake_case}`
convention (messaging-conventions SKILL.md)."""

from __future__ import annotations

import json

import aio_pika

from domain.events.base import DomainEvent

EXCHANGE_NAME = "social.events"

_ROUTING_KEYS: dict[str, str] = {
    "UserFollowed": "social.follow.followed",
    "UserUnfollowed": "social.follow.unfollowed",
}
_FALLBACK_ROUTING_KEY_TEMPLATE = "social.follow.{event_type}"


def routing_key_for(event_type: str) -> str:
    known = _ROUTING_KEYS.get(event_type)
    if known is not None:
        return known
    return _FALLBACK_ROUTING_KEY_TEMPLATE.format(event_type=event_type.lower())


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

    @staticmethod
    def _to_message(event: DomainEvent) -> aio_pika.Message:
        return aio_pika.Message(
            body=json.dumps(event.to_wire()).encode("utf-8"),
            content_type="application/json",
            message_id=str(event.event_id),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

    async def publish(self, event: DomainEvent) -> None:
        await self._exchange.publish(
            self._to_message(event), routing_key=routing_key_for(event.event_type)
        )
