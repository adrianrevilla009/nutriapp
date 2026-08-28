"""IdentityEventsConsumer -- subscribes to identity-service's own
`identity.events` topic exchange (routing key `identity.#`) and dispatches
UserRegistered/PasswordResetRequested/NewDeviceLoginDetected to their
transactional-email command handlers (implementation plan section 1,
acceptance criterion 1). Any other identity event type is acknowledged
and ignored (forward-compatible with future identity events this service
doesn't yet care about).

Idempotent by (event_id, channel="email") -- each handler's own
already-processed check (via ProcessedNotificationsRepositoryPort) is the
single source of truth; this consumer does not duplicate that check.

Failure handling (messaging-conventions SKILL.md): a message that raises
is retried up to MAX_DELIVERY_ATTEMPTS times (a manually incremented
`x-notification-retry-count` header, republished to the same queue and
the original ack'd), then republished to the dead-letter queue instead of
being retried forever or dropped silently. Mirrors
diary-service's diary_event_projector_consumer.py.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import aio_pika
import structlog
from shared_contracts.events.identity import (
    NewDeviceLoginDetectedPayloadV1,
    PasswordResetRequestedPayloadV1,
    UserRegisteredPayloadV1,
)
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.send_new_device_alert import (
    SendNewDeviceAlertCommand,
    SendNewDeviceAlertHandler,
)
from application.commands.send_password_reset_email import (
    SendPasswordResetEmailCommand,
    SendPasswordResetEmailHandler,
)
from application.commands.send_verification_email import (
    SendVerificationEmailCommand,
    SendVerificationEmailHandler,
)
from application.errors import SendNotificationFailedError
from domain.ports.email_provider_port import EmailProviderPort
from domain.ports.template_renderer_port import TemplateRendererPort
from domain.ports.token_reveal_port import TokenRevealPort
from infrastructure.persistence.postgres_delivery_log_repository import (
    PostgresDeliveryLogRepository,
)
from infrastructure.persistence.postgres_processed_notifications_repository import (
    PostgresProcessedNotificationsRepository,
)
from infrastructure.persistence.postgres_suppression_repository import (
    PostgresSuppressionRepository,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "identity.events"
BINDING_ROUTING_KEY = "identity.#"
QUEUE_NAME = "notification-service.identity_events"
DLQ_NAME = "notification-service.identity_events.dlq"
RETRY_HEADER = "x-notification-retry-count"
MAX_DELIVERY_ATTEMPTS = 5


async def dispatch_identity_event(
    session: AsyncSession,
    event_type: str,
    event_id: uuid.UUID,
    payload: dict[str, object],
    correlation_id: str,
    token_reveal: TokenRevealPort,
    email_provider: EmailProviderPort,
    template_renderer: TemplateRendererPort,
) -> None:
    """Shared dispatch helper -- used by the live consumer only today, kept
    as a standalone function (mirroring diary-service's
    apply_event_to_read_models precedent) so any future replay tooling can
    reuse it without re-deriving the dispatch table."""
    processed = PostgresProcessedNotificationsRepository(session)
    delivery_log = PostgresDeliveryLogRepository(session)
    suppression = PostgresSuppressionRepository(session)

    if event_type == "UserRegistered":
        registered = UserRegisteredPayloadV1.model_validate(payload)
        verification_handler = SendVerificationEmailHandler(
            token_reveal, email_provider, template_renderer, processed, delivery_log, suppression
        )
        await verification_handler.handle(
            SendVerificationEmailCommand(
                event_id=event_id,
                user_id=registered.user_id,
                email=registered.email,
                token_reference_id=str(registered.email_verification_token_reference_id),
                correlation_id=correlation_id,
            )
        )
    elif event_type == "PasswordResetRequested":
        reset_requested = PasswordResetRequestedPayloadV1.model_validate(payload)
        reset_handler = SendPasswordResetEmailHandler(
            token_reveal, email_provider, template_renderer, processed, delivery_log, suppression
        )
        await reset_handler.handle(
            SendPasswordResetEmailCommand(
                event_id=event_id,
                user_id=reset_requested.user_id,
                email=reset_requested.email,
                reset_token_reference_id=str(reset_requested.reset_token_reference_id),
                correlation_id=correlation_id,
            )
        )
    elif event_type == "NewDeviceLoginDetected":
        new_device = NewDeviceLoginDetectedPayloadV1.model_validate(payload)
        new_device_handler = SendNewDeviceAlertHandler(
            email_provider, template_renderer, processed, delivery_log, suppression
        )
        await new_device_handler.handle(
            SendNewDeviceAlertCommand(
                event_id=event_id,
                user_id=new_device.user_id,
                email=new_device.email,
                device_fingerprint_hash=new_device.device_fingerprint_hash,
                occurred_at=new_device.occurred_at,
                correlation_id=correlation_id,
            )
        )
    # else: an identity event this service doesn't consume -- ack, ignore.


class IdentityEventsConsumer:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        token_reveal: TokenRevealPort,
        email_provider: EmailProviderPort,
        template_renderer: TemplateRendererPort,
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        self._session_factory = session_factory
        self._token_reveal = token_reveal
        self._email_provider = email_provider
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
            logger.exception("identity_event_processing_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def _process(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        event_id = uuid.UUID(body["event_id"])
        event_type = body["event_type"]
        payload = body["payload"]
        correlation_id = str(body.get("metadata", {}).get("correlation_id") or event_id)

        async with self._session_factory() as session:
            try:
                await dispatch_identity_event(
                    session,
                    event_type,
                    event_id,
                    payload,
                    correlation_id,
                    self._token_reveal,
                    self._email_provider,
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
                "identity_event_dead_lettered", message_id=message.message_id, attempts=attempt
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
