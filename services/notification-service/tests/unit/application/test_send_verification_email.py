"""SendVerificationEmailHandler -- test-plan section 1."""

from __future__ import annotations

import uuid

import pytest

from application.commands.send_verification_email import (
    SendVerificationEmailCommand,
    SendVerificationEmailHandler,
)
from application.errors import SendNotificationFailedError
from domain.ports.email_provider_port import EmailProviderUnavailableError
from domain.ports.token_reveal_port import TokenRevealUnavailableError
from domain.value_objects.notification_category import Channel
from tests.fixtures.factories import (
    FakeDeliveryLogRepositoryPort,
    FakeEmailProviderPort,
    FakeProcessedNotificationsRepositoryPort,
    FakeSuppressionRepositoryPort,
    FakeTemplateRendererPort,
    FakeTokenRevealPort,
)


def _build_handler():
    token_reveal = FakeTokenRevealPort()
    email_provider = FakeEmailProviderPort()
    template_renderer = FakeTemplateRendererPort()
    processed = FakeProcessedNotificationsRepositoryPort()
    delivery_log = FakeDeliveryLogRepositoryPort()
    suppression = FakeSuppressionRepositoryPort()
    handler = SendVerificationEmailHandler(
        token_reveal, email_provider, template_renderer, processed, delivery_log, suppression
    )
    return handler, token_reveal, email_provider, delivery_log, processed, suppression


def _command(event_id: uuid.UUID | None = None) -> SendVerificationEmailCommand:
    return SendVerificationEmailCommand(
        event_id=event_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        email="user@example.com",
        token_reference_id=str(uuid.uuid4()),
        correlation_id="corr-1",
    )


async def test_reveal_succeeds_sends_email_and_marks_processed():
    handler, token_reveal, email_provider, delivery_log, processed, _suppression = _build_handler()
    command = _command()

    await handler.handle(command)

    assert len(email_provider.calls) == 1
    assert email_provider.calls[0]["to"] == command.email
    assert delivery_log.records[-1].status.value == "sent"
    assert await processed.already_processed(command.event_id, "email") is True


async def test_reveal_failure_never_sends_and_logs_failed_and_raises():
    handler, token_reveal, email_provider, delivery_log, processed, _suppression = _build_handler()
    token_reveal.error_to_raise = TokenRevealUnavailableError("circuit open")
    command = _command()

    with pytest.raises(SendNotificationFailedError):
        await handler.handle(command)

    assert len(email_provider.calls) == 0
    assert delivery_log.records[-1].status.value == "failed"
    assert await processed.already_processed(command.event_id, "email") is False


async def test_same_event_id_handled_twice_is_a_noop_second_time():
    handler, token_reveal, email_provider, delivery_log, processed, _suppression = _build_handler()
    command = _command()

    await handler.handle(command)
    await handler.handle(command)

    assert len(token_reveal.calls) == 1
    assert len(email_provider.calls) == 1


async def test_suppressed_recipient_short_circuits_without_reveal_or_send():
    handler, token_reveal, email_provider, delivery_log, processed, suppression = _build_handler()
    command = _command()
    suppression.seed_suppressed(command.user_id, Channel.EMAIL, command.email)

    await handler.handle(command)

    assert len(token_reveal.calls) == 0
    assert len(email_provider.calls) == 0
    assert delivery_log.records == []
    assert await processed.already_processed(command.event_id, "email") is True


async def test_provider_send_failure_logs_failed_and_raises():
    handler, token_reveal, email_provider, delivery_log, processed, _suppression = _build_handler()
    email_provider.error_to_raise = EmailProviderUnavailableError("SES circuit open")
    command = _command()

    with pytest.raises(SendNotificationFailedError):
        await handler.handle(command)

    # The reveal call happened (it must, to render the email) but the
    # send itself failed -- distinct failure point from a reveal failure.
    assert len(token_reveal.calls) == 1
    assert delivery_log.records[-1].status.value == "failed"
    assert await processed.already_processed(command.event_id, "email") is False
