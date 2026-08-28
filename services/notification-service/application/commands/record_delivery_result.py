"""RecordDeliveryResultCommand + handler -- backs the SES/SNS bounce and
complaint webhook (implementation plan section 3,
provider_webhook_routes.py). Hard bounces and explicit unsubscribes are
honored immediately and permanently (docs/notifications.md section 4);
soft bounces are logged but never suppress -- retried via `tenacity`,
exercised at the adapter/integration level, up to a bounded attempt
count. This handler alone never REMOVES a suppression entry -- re-adding
requires a new, separate consent event, out of scope here."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from domain.entities.delivery_log_record import DeliveryLogRecord
from domain.ports.delivery_log_repository_port import DeliveryLogRepositoryPort
from domain.ports.suppression_repository_port import SuppressionRepositoryPort
from domain.value_objects.delivery_status import DeliveryStatus
from domain.value_objects.notification_category import Channel
from domain.value_objects.suppression_reason import SuppressionReason
from domain.value_objects.template_id import TemplateId


class DeliveryOutcome(str, Enum):
    HARD_BOUNCE = "hard_bounce"
    SOFT_BOUNCE = "soft_bounce"
    UNSUBSCRIBE = "unsubscribe"


@dataclass(frozen=True, slots=True)
class RecordDeliveryResultCommand:
    user_id: uuid.UUID
    channel: Channel
    address_or_device: str
    template_id: TemplateId
    outcome: DeliveryOutcome
    detail: str = ""


class RecordDeliveryResultHandler:
    def __init__(
        self,
        delivery_log: DeliveryLogRepositoryPort,
        suppression: SuppressionRepositoryPort,
    ) -> None:
        self._delivery_log = delivery_log
        self._suppression = suppression

    async def handle(self, command: RecordDeliveryResultCommand) -> None:
        now = datetime.now(timezone.utc)

        if command.outcome in (DeliveryOutcome.HARD_BOUNCE, DeliveryOutcome.SOFT_BOUNCE):
            await self._delivery_log.record(
                DeliveryLogRecord(
                    delivery_id=uuid.uuid4(),
                    user_id=command.user_id,
                    channel=command.channel,
                    template_id=command.template_id,
                    status=DeliveryStatus.BOUNCED,
                    attempted_at=now,
                    failure_reason=command.detail or command.outcome.value,
                )
            )

        if command.outcome == DeliveryOutcome.HARD_BOUNCE:
            await self._suppression.add(
                command.user_id,
                command.channel,
                command.address_or_device,
                SuppressionReason.HARD_BOUNCE,
            )
        elif command.outcome == DeliveryOutcome.UNSUBSCRIBE:
            await self._suppression.add(
                command.user_id,
                command.channel,
                command.address_or_device,
                SuppressionReason.UNSUBSCRIBE,
            )
