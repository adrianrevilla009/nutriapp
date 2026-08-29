"""RecordDeliveryResultHandler -- test-plan section 1."""

from __future__ import annotations

import uuid

from application.commands.record_delivery_result import (
    DeliveryOutcome,
    RecordDeliveryResultCommand,
    RecordDeliveryResultHandler,
)
from domain.value_objects.notification_category import Channel
from domain.value_objects.suppression_reason import SuppressionReason
from domain.value_objects.template_id import TemplateId
from tests.fixtures.factories import FakeDeliveryLogRepositoryPort, FakeSuppressionRepositoryPort


def _build():
    delivery_log = FakeDeliveryLogRepositoryPort()
    suppression = FakeSuppressionRepositoryPort()
    handler = RecordDeliveryResultHandler(delivery_log, suppression)
    return handler, delivery_log, suppression


async def test_hard_bounce_logs_bounced_and_suppresses_immediately():
    handler, delivery_log, suppression = _build()
    user_id = uuid.uuid4()

    await handler.handle(
        RecordDeliveryResultCommand(
            user_id=user_id,
            channel=Channel.EMAIL,
            address_or_device="user@example.com",
            template_id=TemplateId("verification", 1),
            outcome=DeliveryOutcome.HARD_BOUNCE,
        )
    )

    assert delivery_log.records[-1].status.value == "bounced"
    assert await suppression.is_suppressed(user_id, Channel.EMAIL, "user@example.com") is True
    assert suppression.added[-1][3] == SuppressionReason.HARD_BOUNCE


async def test_soft_bounce_logs_bounced_but_never_suppresses():
    handler, delivery_log, suppression = _build()
    user_id = uuid.uuid4()

    await handler.handle(
        RecordDeliveryResultCommand(
            user_id=user_id,
            channel=Channel.EMAIL,
            address_or_device="user@example.com",
            template_id=TemplateId("verification", 1),
            outcome=DeliveryOutcome.SOFT_BOUNCE,
        )
    )

    assert delivery_log.records[-1].status.value == "bounced"
    assert await suppression.is_suppressed(user_id, Channel.EMAIL, "user@example.com") is False


async def test_unsubscribe_adds_suppression_with_reason_and_no_delivery_log():
    handler, delivery_log, suppression = _build()
    user_id = uuid.uuid4()

    await handler.handle(
        RecordDeliveryResultCommand(
            user_id=user_id,
            channel=Channel.PUSH,
            address_or_device=str(user_id),
            template_id=TemplateId("fasting_reminder", 1),
            outcome=DeliveryOutcome.UNSUBSCRIBE,
        )
    )

    assert delivery_log.records == []
    assert await suppression.is_suppressed(user_id, Channel.PUSH, str(user_id)) is True
    assert suppression.added[-1][3] == SuppressionReason.UNSUBSCRIBE
