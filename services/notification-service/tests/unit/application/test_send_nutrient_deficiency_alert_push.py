"""SendNutrientDeficiencyAlertPushHandler -- test-plan for the
notification-service half of analytics-service's NutrientDeficiencyDetected
addition (/plans/analytics-service/implementation-plan.md section 6,
two-PR sequencing, same pattern as social-service's UserFollowed ->
SendNewFollowerPushHandler). Idempotency, opt-in-only suppressibility,
suppression-list short-circuit, provider-failure handling, and
quiet-hours-aware delay (a send during quiet hours is persisted as a
PendingPushDispatch row, never dropped, never sent immediately) --
mirrors test_send_new_follower_push.py's shape exactly, adapted for the
analytics-triggered, health-adjacent push category.

NOW is pinned to noon UTC -- outside the default 22:00-08:00 quiet-hours
window -- with every handler under test built with an explicit
`now_fn=lambda: NOW` so the immediate-send cases never race the real wall
clock."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone

import pytest

from application.commands.send_nutrient_deficiency_alert_push import (
    SendNutrientDeficiencyAlertPushCommand,
    SendNutrientDeficiencyAlertPushHandler,
    SendNutrientDeficiencyAlertPushPorts,
)
from application.errors import SendNotificationFailedError
from domain.ports.push_provider_port import PushProviderUnavailableError
from domain.value_objects.notification_category import Channel
from domain.value_objects.pending_dispatch_status import PendingDispatchStatus
from domain.value_objects.quiet_hours_window import QuietHoursWindow
from tests.fixtures.factories import (
    FakeDeliveryLogRepositoryPort,
    FakePendingPushDispatchRepositoryPort,
    FakePreferencesRepositoryPort,
    FakeProcessedNotificationsRepositoryPort,
    FakePushProviderPort,
    FakeSuppressionRepositoryPort,
    FakeTemplateRendererPort,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def _build_handler():
    push_provider = FakePushProviderPort()
    template_renderer = FakeTemplateRendererPort()
    processed = FakeProcessedNotificationsRepositoryPort()
    preferences = FakePreferencesRepositoryPort()
    suppression = FakeSuppressionRepositoryPort()
    delivery_log = FakeDeliveryLogRepositoryPort()
    pending_push_dispatch = FakePendingPushDispatchRepositoryPort()
    ports = SendNutrientDeficiencyAlertPushPorts(
        push_provider=push_provider,
        template_renderer=template_renderer,
        processed_notifications=processed,
        preferences=preferences,
        suppression=suppression,
        delivery_log=delivery_log,
        pending_push_dispatch=pending_push_dispatch,
    )
    handler = SendNutrientDeficiencyAlertPushHandler(ports, now_fn=lambda: NOW)
    return (
        handler,
        push_provider,
        processed,
        preferences,
        suppression,
        delivery_log,
        pending_push_dispatch,
        template_renderer,
    )


def _command(
    event_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None
) -> SendNutrientDeficiencyAlertPushCommand:
    return SendNutrientDeficiencyAlertPushCommand(
        event_id=event_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        signal="protein_g",
        window_days=7,
        value=32.5,
        target_min=50.0,
        sample_size=6,
        disclaimer="This is not a medical diagnosis. Consult a qualified "
        "healthcare professional or registered dietitian for personalized advice.",
        detected_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


async def test_opted_in_user_receives_exactly_one_dispatch():
    handler, push_provider, processed, preferences, _s, delivery_log, _pending, _tr = (
        _build_handler()
    )
    command = _command()
    preferences.seed(command.user_id, "nutrient_deficiency_alert", push_enabled=True)

    await handler.handle(command)

    assert len(push_provider.calls) == 1
    assert push_provider.calls[0]["device_token"] == str(command.user_id)
    assert delivery_log.records[-1].status.value == "sent"
    assert await processed.already_processed(command.event_id, "push") is True


async def test_same_event_id_handled_twice_dispatches_exactly_once():
    handler, push_provider, _p, preferences, _s, _dl, _pending, _tr = _build_handler()
    command = _command()
    preferences.seed(command.user_id, "nutrient_deficiency_alert", push_enabled=True)

    await handler.handle(command)
    await handler.handle(command)

    assert len(push_provider.calls) == 1


async def test_opted_out_user_gets_no_dispatch_attempt():
    handler, push_provider, processed, preferences, _s, delivery_log, _pending, _tr = (
        _build_handler()
    )
    command = _command()
    preferences.seed(command.user_id, "nutrient_deficiency_alert", push_enabled=False)

    await handler.handle(command)

    assert push_provider.calls == []
    assert delivery_log.records == []
    assert await processed.already_processed(command.event_id, "push") is True


async def test_user_with_no_explicit_preference_gets_no_dispatch_attempt():
    # Opt-in only (docs/notifications.md section 2): no explicit preference
    # row must behave identically to an explicit opt-out, same rule as
    # SendNewFollowerPushHandler.
    handler, push_provider, processed, _prefs, _s, delivery_log, _pending, _tr = _build_handler()
    command = _command()

    await handler.handle(command)

    assert push_provider.calls == []
    assert delivery_log.records == []
    assert await processed.already_processed(command.event_id, "push") is True


async def test_suppressed_device_short_circuits_without_send():
    handler, push_provider, processed, preferences, suppression, delivery_log, _pending, _tr = (
        _build_handler()
    )
    command = _command()
    preferences.seed(command.user_id, "nutrient_deficiency_alert", push_enabled=True)
    suppression.seed_suppressed(command.user_id, Channel.PUSH, str(command.user_id))

    await handler.handle(command)

    assert push_provider.calls == []
    assert delivery_log.records == []
    assert await processed.already_processed(command.event_id, "push") is True


async def test_provider_send_failure_logs_failed_and_raises():
    handler, push_provider, processed, preferences, _s, delivery_log, _pending, _tr = (
        _build_handler()
    )
    push_provider.error_to_raise = PushProviderUnavailableError("SNS circuit open")
    command = _command()
    preferences.seed(command.user_id, "nutrient_deficiency_alert", push_enabled=True)

    with pytest.raises(SendNotificationFailedError):
        await handler.handle(command)

    assert delivery_log.records[-1].status.value == "failed"
    assert await processed.already_processed(command.event_id, "push") is False


async def test_quiet_hours_active_persists_pending_row_instead_of_sending():
    handler, push_provider, processed, preferences, _s, delivery_log, pending, _tr = (
        _build_handler()
    )
    command = _command()
    preferences.seed(
        command.user_id,
        "nutrient_deficiency_alert",
        push_enabled=True,
        quiet_hours=QuietHoursWindow(time(10, 0), time(14, 0), "UTC"),
    )

    await handler.handle(command)

    assert push_provider.calls == []
    assert delivery_log.records == []
    assert len(pending.added) == 1
    persisted = pending.added[0]
    assert persisted.user_id == command.user_id
    assert persisted.template_id.name == "nutrient_deficiency_alert"
    assert persisted.earliest_dispatch_at > NOW
    assert persisted.status == PendingDispatchStatus.PENDING
    assert await processed.already_processed(command.event_id, "push") is True


async def test_quiet_hours_active_same_event_id_replayed_persists_exactly_one_pending_row():
    handler, push_provider, _p, preferences, _s, _dl, pending, _tr = _build_handler()
    command = _command()
    preferences.seed(
        command.user_id,
        "nutrient_deficiency_alert",
        push_enabled=True,
        quiet_hours=QuietHoursWindow(time(10, 0), time(14, 0), "UTC"),
    )

    await handler.handle(command)
    await handler.handle(command)

    assert push_provider.calls == []
    assert len(pending.added) == 1


async def test_not_in_quiet_hours_still_dispatches_immediately():
    handler, push_provider, processed, preferences, _s, delivery_log, pending, _tr = (
        _build_handler()
    )
    command = _command()
    preferences.seed(command.user_id, "nutrient_deficiency_alert", push_enabled=True)

    await handler.handle(command)

    assert len(push_provider.calls) == 1
    assert delivery_log.records[-1].status.value == "sent"
    assert pending.added == []
    assert await processed.already_processed(command.event_id, "push") is True


async def test_render_context_never_includes_raw_disclaimer_field_directly():
    # The template renders a static, versioned disclaimer sentence (this
    # service's own reviewed copy, CLAUDE.md section 8), not
    # analytics-service's own `disclaimer` payload string verbatim --
    # content must never be constructed straight from an upstream event
    # payload (module docstring of send_new_follower_push.py's sibling
    # module, docs/notifications.md section 3). The upstream disclaimer
    # text is not forwarded into the render context at all.
    handler, _pp, _processed, preferences, _s, _dl, _pending, template_renderer = _build_handler()
    command = _command()
    preferences.seed(command.user_id, "nutrient_deficiency_alert", push_enabled=True)

    await handler.handle(command)

    assert len(template_renderer.push_calls) == 1
    _template_id, context = template_renderer.push_calls[0]
    assert "disclaimer" not in context
