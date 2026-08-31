"""SendNewFollowerPushHandler -- test-plan section 6 (notification-service
PR A of the social-service initiative): idempotency, opt-in-only
suppressibility (a user who never explicitly enabled the category gets no
dispatch attempt, same as one who explicitly disabled it), suppression-list
short-circuit, provider-failure handling, and (PR B, the quiet-hours fix)
the quiet-hours-aware delay: a send during quiet hours is persisted as a
`PendingPushDispatch` row instead of being sent immediately or dropped, and
a send outside quiet hours still dispatches immediately (regression).
Mirrors test_send_new_device_alert.py's shape for the transactional-email
counterpart, adapted for a non-transactional, preference-gated push.

NOW is pinned to noon UTC -- outside the default 22:00-08:00 quiet-hours
window -- and every handler under test is built with an explicit
`now_fn=lambda: NOW` so none of these cases race the real wall clock
(a bare `datetime.now(timezone.utc)` default would make the immediate-send
cases flaky for ~10 of every 24 hours once quiet-hours gating exists)."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone

import pytest

from application.commands.send_new_follower_push import (
    SendNewFollowerPushCommand,
    SendNewFollowerPushHandler,
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

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _build_handler():
    push_provider = FakePushProviderPort()
    template_renderer = FakeTemplateRendererPort()
    processed = FakeProcessedNotificationsRepositoryPort()
    preferences = FakePreferencesRepositoryPort()
    suppression = FakeSuppressionRepositoryPort()
    delivery_log = FakeDeliveryLogRepositoryPort()
    pending_push_dispatch = FakePendingPushDispatchRepositoryPort()
    handler = SendNewFollowerPushHandler(
        push_provider,
        template_renderer,
        processed,
        preferences,
        suppression,
        delivery_log,
        pending_push_dispatch,
        now_fn=lambda: NOW,
    )
    return (
        handler,
        push_provider,
        processed,
        preferences,
        suppression,
        delivery_log,
        pending_push_dispatch,
    )


def _command(
    event_id: uuid.UUID | None = None, followee_id: uuid.UUID | None = None
) -> SendNewFollowerPushCommand:
    return SendNewFollowerPushCommand(
        event_id=event_id or uuid.uuid4(),
        follow_id=uuid.uuid4(),
        follower_id=uuid.uuid4(),
        followee_id=followee_id or uuid.uuid4(),
        followed_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


async def test_opted_in_followee_receives_exactly_one_dispatch():
    handler, push_provider, processed, preferences, _s, delivery_log, _pending = _build_handler()
    command = _command()
    preferences.seed(command.followee_id, "new_follower", push_enabled=True)

    await handler.handle(command)

    assert len(push_provider.calls) == 1
    assert push_provider.calls[0]["device_token"] == str(command.followee_id)
    assert delivery_log.records[-1].status.value == "sent"
    assert await processed.already_processed(command.event_id, "push") is True


async def test_same_event_id_handled_twice_dispatches_exactly_once():
    handler, push_provider, _p, preferences, _s, _dl, _pending = _build_handler()
    command = _command()
    preferences.seed(command.followee_id, "new_follower", push_enabled=True)

    await handler.handle(command)
    await handler.handle(command)

    assert len(push_provider.calls) == 1


async def test_opted_out_followee_gets_no_dispatch_attempt():
    handler, push_provider, processed, preferences, _s, delivery_log, _pending = _build_handler()
    command = _command()
    preferences.seed(command.followee_id, "new_follower", push_enabled=False)

    await handler.handle(command)

    assert push_provider.calls == []
    assert delivery_log.records == []
    assert await processed.already_processed(command.event_id, "push") is True


async def test_followee_with_no_explicit_preference_gets_no_dispatch_attempt():
    # Opt-in only (module docstring): no explicit preference row is not
    # the same as an implicit "on".
    handler, push_provider, processed, _prefs, _s, delivery_log, _pending = _build_handler()
    command = _command()

    await handler.handle(command)

    assert push_provider.calls == []
    assert delivery_log.records == []
    assert await processed.already_processed(command.event_id, "push") is True


async def test_suppressed_device_short_circuits_without_send():
    handler, push_provider, processed, preferences, suppression, delivery_log, _pending = (
        _build_handler()
    )
    command = _command()
    preferences.seed(command.followee_id, "new_follower", push_enabled=True)
    suppression.seed_suppressed(command.followee_id, Channel.PUSH, str(command.followee_id))

    await handler.handle(command)

    assert push_provider.calls == []
    assert delivery_log.records == []
    assert await processed.already_processed(command.event_id, "push") is True


async def test_provider_send_failure_logs_failed_and_raises():
    handler, push_provider, processed, preferences, _s, delivery_log, _pending = _build_handler()
    push_provider.error_to_raise = PushProviderUnavailableError("SNS circuit open")
    command = _command()
    preferences.seed(command.followee_id, "new_follower", push_enabled=True)

    with pytest.raises(SendNotificationFailedError):
        await handler.handle(command)

    assert delivery_log.records[-1].status.value == "failed"
    assert await processed.already_processed(command.event_id, "push") is False


async def test_never_dispatches_to_the_follower_only_the_followee():
    handler, push_provider, _p, preferences, _s, _dl, _pending = _build_handler()
    command = _command()
    preferences.seed(command.followee_id, "new_follower", push_enabled=True)
    # A follower-side preference row (even enabled) must never trigger a
    # send -- the recipient is always the followee.
    preferences.seed(command.follower_id, "new_follower", push_enabled=True)

    await handler.handle(command)

    assert len(push_provider.calls) == 1
    assert push_provider.calls[0]["device_token"] == str(command.followee_id)


async def test_quiet_hours_active_persists_pending_row_instead_of_sending():
    # NOW (noon UTC) falls inside a 10:00-14:00 quiet-hours window --
    # architecture-agent's BLOCKED finding: never dispatched immediately,
    # never dropped, delayed to the next allowed window instead.
    handler, push_provider, processed, preferences, _s, delivery_log, pending = _build_handler()
    command = _command()
    preferences.seed(
        command.followee_id,
        "new_follower",
        push_enabled=True,
        quiet_hours=QuietHoursWindow(time(10, 0), time(14, 0), "UTC"),
    )

    await handler.handle(command)

    assert push_provider.calls == []
    assert delivery_log.records == []
    assert len(pending.added) == 1
    persisted = pending.added[0]
    assert persisted.user_id == command.followee_id
    assert persisted.template_id.name == "new_follower"
    assert persisted.earliest_dispatch_at > NOW
    assert persisted.status == PendingDispatchStatus.PENDING
    # Still marked processed -- a redelivery of the same triggering event
    # must not persist a second pending row (idempotency covers both the
    # immediate-send and the deferred-dispatch path).
    assert await processed.already_processed(command.event_id, "push") is True


async def test_quiet_hours_active_same_event_id_replayed_persists_exactly_one_pending_row():
    handler, push_provider, _p, preferences, _s, _dl, pending = _build_handler()
    command = _command()
    preferences.seed(
        command.followee_id,
        "new_follower",
        push_enabled=True,
        quiet_hours=QuietHoursWindow(time(10, 0), time(14, 0), "UTC"),
    )

    await handler.handle(command)
    await handler.handle(command)

    assert push_provider.calls == []
    assert len(pending.added) == 1


async def test_not_in_quiet_hours_still_dispatches_immediately():
    # Regression check: the default 22:00-08:00 quiet-hours window does not
    # contain NOW (noon UTC), so this must behave exactly as it did before
    # the quiet-hours fix -- an immediate dispatch, no pending row.
    handler, push_provider, processed, preferences, _s, delivery_log, pending = _build_handler()
    command = _command()
    preferences.seed(command.followee_id, "new_follower", push_enabled=True)

    await handler.handle(command)

    assert len(push_provider.calls) == 1
    assert delivery_log.records[-1].status.value == "sent"
    assert pending.added == []
    assert await processed.already_processed(command.event_id, "push") is True

