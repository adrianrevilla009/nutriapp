"""SendVerificationEmailCommand + handler -- reacts to identity-service's
UserRegistered event (implementation plan section 1, acceptance criterion
1). Reveals the raw verification secret via TokenRevealPort, renders the
versioned verification email template, sends via EmailProviderPort.
Never sends a half-rendered email: the reveal call happens before any
render/send, and any failure is logged + raised, never silently dropped.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import SendNotificationFailedError
from domain.entities.delivery_log_record import DeliveryLogRecord
from domain.ports.delivery_log_repository_port import DeliveryLogRepositoryPort
from domain.ports.email_provider_port import EmailProviderPort, EmailProviderUnavailableError
from domain.ports.processed_notifications_repository_port import (
    ProcessedNotificationsRepositoryPort,
)
from domain.ports.suppression_repository_port import SuppressionRepositoryPort
from domain.ports.template_renderer_port import TemplateRendererPort
from domain.ports.token_reveal_port import (
    TokenRevealNotFoundError,
    TokenRevealPort,
    TokenRevealUnavailableError,
)
from domain.value_objects.delivery_status import DeliveryStatus
from domain.value_objects.notification_category import Channel
from domain.value_objects.template_id import TemplateId

CHANNEL = "email"
TEMPLATE_ID = TemplateId("verification", 1)
_REVEAL_ERRORS = (TokenRevealUnavailableError, TokenRevealNotFoundError)


@dataclass(frozen=True, slots=True)
class SendVerificationEmailCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    token_reference_id: str
    correlation_id: str


class SendVerificationEmailHandler:
    def __init__(
        self,
        token_reveal: TokenRevealPort,
        email_provider: EmailProviderPort,
        template_renderer: TemplateRendererPort,
        processed_notifications: ProcessedNotificationsRepositoryPort,
        delivery_log: DeliveryLogRepositoryPort,
        suppression: SuppressionRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._token_reveal = token_reveal
        self._email_provider = email_provider
        self._template_renderer = template_renderer
        self._processed = processed_notifications
        self._delivery_log = delivery_log
        self._suppression = suppression
        self._now_fn = now_fn

    async def handle(self, command: SendVerificationEmailCommand) -> None:
        if await self._processed.already_processed(command.event_id, CHANNEL):
            return
        if await self._suppression.is_suppressed(command.user_id, Channel.EMAIL, command.email):
            await self._processed.mark_processed(command.event_id, CHANNEL)
            return

        try:
            revealed = await self._token_reveal.reveal(command.token_reference_id)
        except _REVEAL_ERRORS as exc:
            await self._log_failure(command, str(exc))
            raise SendNotificationFailedError(
                "Could not reveal the verification token secret."
            ) from exc

        rendered = self._template_renderer.render_email(
            TEMPLATE_ID, {"email": command.email, "verification_token": revealed.secret}
        )

        try:
            await self._email_provider.send(
                to=command.email,
                subject=rendered.subject,
                html_body=rendered.html_body,
                correlation_id=command.correlation_id,
            )
        except EmailProviderUnavailableError as exc:
            await self._log_failure(command, str(exc))
            raise SendNotificationFailedError("Could not send the verification email.") from exc

        await self._delivery_log.record(
            DeliveryLogRecord(
                delivery_id=uuid.uuid4(),
                user_id=command.user_id,
                channel=Channel.EMAIL,
                template_id=TEMPLATE_ID,
                status=DeliveryStatus.SENT,
                attempted_at=self._now_fn(),
            )
        )
        await self._processed.mark_processed(command.event_id, CHANNEL)

    async def _log_failure(self, command: SendVerificationEmailCommand, reason: str) -> None:
        await self._delivery_log.record(
            DeliveryLogRecord(
                delivery_id=uuid.uuid4(),
                user_id=command.user_id,
                channel=Channel.EMAIL,
                template_id=TEMPLATE_ID,
                status=DeliveryStatus.FAILED,
                attempted_at=self._now_fn(),
                failure_reason=reason,
            )
        )
