"""ScanAndSendPendingPushDispatchesHandler -- mirrors
test_scan_and_send_due_reminders.py's shape for the one-shot
pending_push_dispatch mechanism: a due row is sent and marked SENT; a
still-in-quiet-hours row is rescheduled, never sent; a row already SENT is
never dispatched twice on a later scan tick (idempotency); an opted-out or
suppressed row is marked SUPPRESSED with no provider call; a provider
failure leaves the row PENDING for the next tick."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from application.commands.scan_and_send_pending_push_dispatches import (
    ScanAndSendPendingPushDispatchesHandler,
)
from domain.ports.push_provider_port import PushProviderUnavailableError
from domain.value_objects.notification_category import Channel
from domain.value_objects.pending_dispatch_status import PendingDispatchStatus
from domain.value_objects.quiet_hours_window import QuietHoursWindow
from tests.fixtures.factories import (
    FakeDeliveryLogRepositoryPort,
    FakePendingPushDispatchRepositoryPort,
    FakePreferencesRepositoryPort,
    FakePushProviderPort,
    FakeSuppressionRepositoryPort,
    FakeTemplateRendererPort,
    make_pending_push_dispatch,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _build():
    pending_push_dispatch = FakePendingPushDispatchRepositoryPort()
    preferences = FakePreferencesRepositoryPort()
    push_provider = FakePushProviderPort()
    suppression = FakeSuppressionRepositoryPort()
    template_renderer = FakeTemplateRendererPort()
    delivery_log = FakeDeliveryLogRepositoryPort()
    handler = ScanAndSendPendingPushDispatchesHandler(
        pending_push_dispatch,
        preferences,
        push_provider,
        suppression,
        template_renderer,
        delivery_log,
    )
    return handler, pending_push_dispatch, preferences, push_provider, suppression, delivery_log


async def test_due_pending_row_is_sent_and_marked_sent():
    handler, pending_push_dispatch, preferences, push_provider, _s, delivery_log = _build()
    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
    pending_push_dispatch.seed(dispatch)
    preferences.seed(dispatch.user_id, "new_follower", push_enabled=True)

    await handler.handle(NOW)

    assert len(push_provider.calls) == 1
    assert push_provider.calls[0]["device_token"] == str(dispatch.user_id)
    assert delivery_log.records[-1].status.value == "sent"
    stored = pending_push_dispatch._by_id[dispatch.dispatch_id]
    assert stored.status == PendingDispatchStatus.SENT


async def test_row_already_sent_is_never_dispatched_twice():
    handler, pending_push_dispatch, preferences, push_provider, _s, _dl = _build()
    dispatch = make_pending_push_dispatch(
        earliest_dispatch_at=NOW - timedelta(minutes=5),
        status=PendingDispatchStatus.SENT,
    )
    pending_push_dispatch.seed(dispatch)
    preferences.seed(dispatch.user_id, "new_follower", push_enabled=True)

    await handler.handle(NOW)

    assert push_provider.calls == []


async def test_scanning_twice_after_a_successful_send_dispatches_exactly_once():
    handler, pending_push_dispatch, preferences, push_provider, _s, _dl = _build()
    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
    pending_push_dispatch.seed(dispatch)
    preferences.seed(dispatch.user_id, "new_follower", push_enabled=True)

    await handler.handle(NOW)
    await handler.handle(NOW + timedelta(minutes=1))

    assert len(push_provider.calls) == 1


async def test_not_yet_due_row_is_left_alone():
    handler, pending_push_dispatch, preferences, push_provider, _s, _dl = _build()
    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW + timedelta(hours=1))
    pending_push_dispatch.seed(dispatch)
    preferences.seed(dispatch.user_id, "new_follower", push_enabled=True)

    await handler.handle(NOW)

    assert push_provider.calls == []
    stored = pending_push_dispatch._by_id[dispatch.dispatch_id]
    assert stored.status == PendingDispatchStatus.PENDING


async def test_still_in_quiet_hours_at_scan_time_is_rescheduled_not_sent():
    handler, pending_push_dispatch, preferences, push_provider, _s, _dl = _build()
    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
    pending_push_dispatch.seed(dispatch)
    preferences.seed(
        dispatch.user_id,
        "new_follower",
        push_enabled=True,
        quiet_hours=QuietHoursWindow(time(10, 0), time(14, 0), "UTC"),
    )

    await handler.handle(NOW)

    assert push_provider.calls == []
    stored = pending_push_dispatch._by_id[dispatch.dispatch_id]
    assert stored.status == PendingDispatchStatus.PENDING
    assert stored.earliest_dispatch_at > NOW


async def test_opted_out_by_scan_time_is_suppressed_no_send():
    handler, pending_push_dispatch, preferences, push_provider, _s, delivery_log = _build()
    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
    pending_push_dispatch.seed(dispatch)
    preferences.seed(dispatch.user_id, "new_follower", push_enabled=False)

    await handler.handle(NOW)

    assert push_provider.calls == []
    assert delivery_log.records == []
    stored = pending_push_dispatch._by_id[dispatch.dispatch_id]
    assert stored.status == PendingDispatchStatus.SUPPRESSED


async def test_suppressed_device_by_scan_time_is_checked_before_provider_call():
    handler, pending_push_dispatch, preferences, push_provider, suppression, _dl = _build()
    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
    pending_push_dispatch.seed(dispatch)
    preferences.seed(dispatch.user_id, "new_follower", push_enabled=True)
    suppression.seed_suppressed(dispatch.user_id, Channel.PUSH, str(dispatch.user_id))

    await handler.handle(NOW)

    assert push_provider.calls == []
    stored = pending_push_dispatch._by_id[dispatch.dispatch_id]
    assert stored.status == PendingDispatchStatus.SUPPRESSED


async def test_provider_failure_leaves_row_pending_for_next_tick():
    handler, pending_push_dispatch, preferences, push_provider, _s, delivery_log = _build()
    push_provider.error_to_raise = PushProviderUnavailableError("SNS circuit open")
    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
    pending_push_dispatch.seed(dispatch)
    preferences.seed(dispatch.user_id, "new_follower", push_enabled=True)

    await handler.handle(NOW)

    assert delivery_log.records[-1].status.value == "failed"
    stored = pending_push_dispatch._by_id[dispatch.dispatch_id]
    assert stored.status == PendingDispatchStatus.PENDING
