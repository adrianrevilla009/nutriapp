"""RabbitMqEventPublisher -- implements EventPublisherPort.

Naming convention (messaging-conventions SKILL.md, CLAUDE.md section 2.4):
`{service}.{aggregate}.{event_type}`, e.g. `diary.food_entry.logged` --
the exchange is `diary.events` (topic), routing keys follow the table
below (one entry per event type this service publishes).
"""

from __future__ import annotations

import json

import aio_pika

from domain.events.base import DomainEvent

EXCHANGE_NAME = "diary.events"

_ROUTING_KEY_BY_EVENT_TYPE = {
    "FoodEntryLogged": "diary.food_entry.logged",
    "FoodEntryCorrected": "diary.food_entry.corrected",
    "FoodEntryDeleted": "diary.food_entry.deleted",
    "WaterIntakeLogged": "diary.water_intake.logged",
    "WaterIntakeRemoved": "diary.water_intake.removed",
    "FastingWindowStarted": "diary.fasting_window.started",
    "FastingWindowEnded": "diary.fasting_window.ended",
    "MealPlanned": "diary.meal_plan.planned",
    "MealPlanUpdated": "diary.meal_plan.updated",
    "MealPlanRemoved": "diary.meal_plan.removed",
}


def routing_key_for(event_type: str) -> str:
    try:
        return _ROUTING_KEY_BY_EVENT_TYPE[event_type]
    except KeyError as exc:
        raise ValueError(f"No routing key configured for event_type {event_type!r}.") from exc


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
