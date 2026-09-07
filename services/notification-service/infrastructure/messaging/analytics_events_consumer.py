"""AnalyticsEventsConsumer -- subscribes to analytics-service's own
`analytics.events` topic exchange (routing key `analytics.#`) and
dispatches `NutrientDeficiencyDetected` (v1) to
SendNutrientDeficiencyAlertPushHandler
(/plans/analytics-service/implementation-plan.md section 6, two-PR
sequencing: this consumer is wired and merged BEFORE analytics-service's
own PR, so the event is never live with zero consumers -- same pattern
`social-service`'s `UserFollowed` -> `notification-service` addition
used). Any other analytics event this service doesn't consume is
acknowledged and ignored -- forward-compatible with future analytics
events.

`NutrientDeficiencyDetectedPayloadV1` is defined locally rather than
imported from `packages/shared-contracts` because there is no
`shared_contracts.events.analytics` Python module published yet at the
time this PR is built -- only the JSON Schema
(`packages/shared-contracts/schemas/nutrient_deficiency_detected.v1.json`)
exists, and this model is built and tested directly against that schema
plus a fixture event (see tests/contract/events/test_event_schemas.py),
no live analytics-service required. Mirrors
social_events_consumer.py's identical precedent and its own flagged
follow-up: once analytics-service exists and publishes for real, migrate
this to a shared_contracts.events.analytics module for consistency with
diary_events_consumer.py's/identity_events_consumer.py's precedent.

Idempotent by (event_id, channel="push") --
SendNutrientDeficiencyAlertPushHandler's own
ProcessedNotificationsRepositoryPort check is the single source of truth;
this consumer does not duplicate that check (identity_events_consumer.py's
identical precedent).

Failure handling: same retry/DLQ shape as social_events_consumer.py,
diary_events_consumer.py, and identity_events_consumer.py.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime

import aio_pika
import structlog
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.send_nutrient_deficiency_alert_push import (
    SendNutrientDeficiencyAlertPushCommand,
    SendNutrientDeficiencyAlertPushHandler,
)
from application.errors import SendNotificationFailedError
from domain.ports.push_provider_port import PushProviderPort
from domain.ports.template_renderer_port import TemplateRendererPort
from infrastructure.persistence.postgres_delivery_log_repository import (
    PostgresDeliveryLogRepository,
)
from infrastructure.persistence.postgres_pending_push_dispatch_repository import (
    PostgresPendingPushDispatchRepository,
)
from infrastructure.persistence.postgres_preferences_repository import (
    PostgresPreferencesRepository,
)
from infrastructure.persistence.postgres_processed_notifications_repository import (
    PostgresProcessedNotificationsRepository,
)
from infrastructure.persistence.postgres_suppression_repository import (
    PostgresSuppressionRepository,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "analytics.events"
BINDING_ROUTING_KEY = "analytics.#"
QUEUE_NAME = "notification-service.analytics_events"
DLQ_NAME = "notification-service.analytics_events.dlq"
RETRY_HEADER = "x-notification-retry-count"
MAX_DELIVERY_ATTEMPTS = 5


class NutrientDeficiencyDetectedPayloadV1(BaseModel):
    """Matches analytics-service's NutrientDeficiencyDetected (v1) payload
    shape exactly, per
    packages/shared-contracts/schemas/nutrient_deficiency_detected.v1.json
    -- built and tested against a fixture event, no real analytics-service
    required (see module docstring)."""

    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    signal: str
    window_days: int
    value: float
    target_min: float
    sample_size: int
    disclaimer: str


async def dispatch_analytics_event(
    session: AsyncSession,
    event_type: str,
    event_id: uuid.UUID,
    occurred_at: datetime,
    payload: dict[str, object],
    correlation_id: str,
    push_provider: PushProviderPort,
    template_renderer: TemplateRendererPort,
) -> None:
    """Shared dispatch helper -- used by the live consumer only today, kept
    as a standalone function (mirroring social_events_consumer.py's
    identical precedent) so any future replay tooling can reuse it without
    re-deriving the dispatch table."""
    processed = PostgresProcessedNotificationsRepository(session)
    preferences = PostgresPreferencesRepository(session)
    suppression = PostgresSuppressionRepository(session)
    delivery_log = PostgresDeliveryLogRepository(session)
    pending_push_dispatch = PostgresPendingPushDispatchRepository(session)

    if event_type == "NutrientDeficiencyDetected":
        detected = NutrientDeficiencyDetectedPayloadV1.model_validate(payload)
        handler = SendNutrientDeficiencyAlertPushHandler(
            push_provider,
            template_renderer,
            processed,
            preferences,
            suppression,
            delivery_log,
            pending_push_dispatch,
        )
        await handler.handle(
            SendNutrientDeficiencyAlertPushCommand(
                event_id=event_id,
                user_id=detected.user_id,
                signal=detected.signal,
                window_days=detected.window_days,
                value=detected.value,
                target_min=detected.target_min,
                sample_size=detected.sample_size,
                disclaimer=detected.disclaimer,
                detected_at=occurred_at,
                correlation_id=correlation_id,
            )
        )
    # else: an analytics event this service doesn't consume -- ack, ignore.


class AnalyticsEventsConsumer:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        push_provider: PushProviderPort,
        template_renderer: TemplateRendererPort,
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        self._session_factory = session_factory
        self._push_provider = push_provider
        self._template_renderer = template_renderer
        self._max_attempts = max_attempts
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None

    async def setup(
        self, connection: aio_pika.abc.AbstractRobustConnection
    ) -> aio_pika.abc.AbstractQueue:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=20)
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        await channel.declare_queue(DLQ_NAME, durable=True)
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=BINDING_ROUTING_KEY)

        self._channel = channel
        self._queue = queue
        return queue

    async def consume(self) -> None:
        assert self._queue is not None, "call setup() first"
        await self._queue.consume(self.on_message, no_ack=False)

    async def on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            await self._process(message)
            await message.ack()
        except Exception:
            logger.exception("analytics_event_processing_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def _process(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        event_id = uuid.UUID(body["event_id"])
        event_type = body["event_type"]
        payload = body["payload"]
        occurred_at = datetime.fromisoformat(body["occurred_at"])
        correlation_id = str(body.get("metadata", {}).get("correlation_id") or event_id)

        async with self._session_factory() as session:
            try:
                await dispatch_analytics_event(
                    session,
                    event_type,
                    event_id,
                    occurred_at,
                    payload,
                    correlation_id,
                    self._push_provider,
                    self._template_renderer,
                )
            except SendNotificationFailedError:
                # Persist whatever the handler already logged (e.g. a
                # FAILED delivery_log row) before propagating so the
                # retry/DLQ path still sees an accurate audit trail.
                await session.commit()
                raise
            else:
                await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "analytics_event_dead_lettered", message_id=message.message_id, attempts=attempt
            )
        else:
            target_queue_name = QUEUE_NAME
            headers[RETRY_HEADER] = attempt

        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=headers,
                content_type=message.content_type,
                message_id=message.message_id,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=target_queue_name,
        )
        await message.ack()
