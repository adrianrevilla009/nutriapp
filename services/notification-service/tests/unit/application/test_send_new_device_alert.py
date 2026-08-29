"""SendNewDeviceAlertHandler -- test-plan section 1: no reveal call, ever
(the constructor doesn't even accept a TokenRevealPort -- a structural
guarantee, asserted via introspection below), brought up to parity with
SendVerificationEmailHandler's/SendPasswordResetEmailHandler's test files
(idempotency, suppression short-circuit, provider-failure)."""

from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone

import pytest

from application.commands.send_new_device_alert import (
    SendNewDeviceAlertCommand,
    SendNewDeviceAlertHandler,
)
from application.errors import SendNotificationFailedError
from domain.ports.email_provider_port import EmailProviderUnavailableError
from domain.value_objects.notification_category import Channel
from tests.fixtures.factories import (
    FakeDeliveryLogRepositoryPort,
    FakeEmailProviderPort,
    FakeProcessedNotificationsRepositoryPort,
    FakeSuppressionRepositoryPort,
    FakeTemplateRendererPort,
)


def _build_handler():
    email_provider = FakeEmailProviderPort()
    template_renderer = FakeTemplateRendererPort()
    processed = FakeProcessedNotificationsRepositoryPort()
    delivery_log = FakeDeliveryLogRepositoryPort()
    suppression = FakeSuppressionRepositoryPort()
    handler = SendNewDeviceAlertHandler(
        email_provider, template_renderer, processed, delivery_log, suppression
    )
    return handler, email_provider, delivery_log, processed, suppression


def _command(event_id: uuid.UUID | None = None) -> SendNewDeviceAlertCommand:
    return SendNewDeviceAlertCommand(
        event_id=event_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        email="user@example.com",
        device_fingerprint_hash="abc123",
        occurred_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


def test_constructor_never_accepts_a_token_reveal_port():
    params = inspect.signature(SendNewDeviceAlertHandler.__init__).parameters
    assert "token_reveal" not in params


async def test_alert_uses_payload_email_directly_no_reveal_call():
    handler, email_provider, delivery_log, processed, _suppression = _build_handler()
    command = _command()

    await handler.handle(command)

    assert len(email_provider.calls) == 1
    assert email_provider.calls[0]["to"] == "user@example.com"
    assert delivery_log.records[-1].status.value == "sent"
    assert await processed.already_processed(command.event_id, "email") is True


async def test_same_event_id_handled_twice_is_a_noop_second_time():
    handler, email_provider, delivery_log, processed, _suppression = _build_handler()
    command = _command()

    await handler.handle(command)
    await handler.handle(command)

    assert len(email_provider.calls) == 1


async def test_suppressed_recipient_short_circuits_without_send():
    handler, email_provider, delivery_log, processed, suppression = _build_handler()
    command = _command()
    suppression.seed_suppressed(command.user_id, Channel.EMAIL, command.email)

    await handler.handle(command)

    assert len(email_provider.calls) == 0
    assert delivery_log.records == []
    assert await processed.already_processed(command.event_id, "email") is True


async def test_provider_send_failure_logs_failed_and_raises():
    handler, email_provider, delivery_log, processed, _suppression = _build_handler()
    email_provider.error_to_raise = EmailProviderUnavailableError("SES circuit open")
    command = _command()

    with pytest.raises(SendNotificationFailedError):
        await handler.handle(command)

    assert delivery_log.records[-1].status.value == "failed"
    assert await processed.already_processed(command.event_id, "email") is False
