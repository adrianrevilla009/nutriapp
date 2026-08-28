"""ScanAndSendDueRemindersHandler -- test-plan section 1's five cases."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from application.commands.scan_and_send_due_reminders import ScanAndSendDueRemindersHandler
from domain.value_objects.notification_category import Channel
from domain.value_objects.quiet_hours_window import QuietHoursWindow
from domain.value_objects.reminder_status import ReminderStatus
from tests.fixtures.factories import (
    FakeDeliveryLogRepositoryPort,
    FakePreferencesRepositoryPort,
    FakePushProviderPort,
    FakeReminderScheduleRepositoryPort,
    FakeSuppressionRepositoryPort,
    FakeTemplateRendererPort,
    make_reminder_entry,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _build():
    reminder_schedule = FakeReminderScheduleRepositoryPort()
    preferences = FakePreferencesRepositoryPort()
    push_provider = FakePushProviderPort()
    suppression = FakeSuppressionRepositoryPort()
    template_renderer = FakeTemplateRendererPort()
    delivery_log = FakeDeliveryLogRepositoryPort()
    handler = ScanAndSendDueRemindersHandler(
        reminder_schedule, preferences, push_provider, suppression, template_renderer, delivery_log
    )
    return handler, reminder_schedule, preferences, push_provider, suppression, delivery_log


async def test_due_non_suppressed_enabled_non_quiet_hours_is_sent():
    handler, reminder_schedule, preferences, push_provider, suppression, delivery_log = _build()
    entry = make_reminder_entry(
        due_at=NOW - timedelta(minutes=5), relevance_expires_at=NOW + timedelta(hours=1)
    )
    reminder_schedule.seed(entry)
    preferences.seed(
        entry.user_id,
        "fasting",
        push_enabled=True,
        quiet_hours=QuietHoursWindow(start=time(22, 0), end=time(8, 0), tz="UTC"),
    )

    await handler.handle(NOW)

    assert len(push_provider.calls) == 1
    updated = await reminder_schedule.get_by_source(entry.source_aggregate_id, "fasting")
    assert updated.status == ReminderStatus.SENT


async def test_due_row_with_category_disabled_is_suppressed_no_send():
    handler, reminder_schedule, preferences, push_provider, suppression, delivery_log = _build()
    entry = make_reminder_entry(
        due_at=NOW - timedelta(minutes=5), relevance_expires_at=NOW + timedelta(hours=1)
    )
    reminder_schedule.seed(entry)
    preferences.seed(entry.user_id, "fasting", push_enabled=False)

    await handler.handle(NOW)

    assert len(push_provider.calls) == 0
    updated = await reminder_schedule.get_by_source(entry.source_aggregate_id, "fasting")
    assert updated.status == ReminderStatus.SUPPRESSED


async def test_due_row_for_suppressed_user_is_checked_before_provider_call():
    handler, reminder_schedule, preferences, push_provider, suppression, delivery_log = _build()
    entry = make_reminder_entry(
        due_at=NOW - timedelta(minutes=5), relevance_expires_at=NOW + timedelta(hours=1)
    )
    reminder_schedule.seed(entry)
    preferences.seed(entry.user_id, "fasting", push_enabled=True)
    suppression.seed_suppressed(entry.user_id, Channel.PUSH, str(entry.user_id))

    await handler.handle(NOW)

    assert len(push_provider.calls) == 0
    updated = await reminder_schedule.get_by_source(entry.source_aggregate_id, "fasting")
    assert updated.status == ReminderStatus.SUPPRESSED


async def test_due_row_during_quiet_hours_is_delayed_not_dropped():
    handler, reminder_schedule, preferences, push_provider, suppression, delivery_log = _build()
    entry = make_reminder_entry(
        due_at=NOW - timedelta(minutes=5), relevance_expires_at=NOW + timedelta(hours=1)
    )
    reminder_schedule.seed(entry)
    # NOW (12:00 UTC) falls inside a 10:00-14:00 quiet-hours window.
    preferences.seed(
        entry.user_id,
        "fasting",
        push_enabled=True,
        quiet_hours=QuietHoursWindow(time(10, 0), time(14, 0), "UTC"),
    )

    await handler.handle(NOW)

    assert len(push_provider.calls) == 0
    updated = await reminder_schedule.get_by_source(entry.source_aggregate_id, "fasting")
    assert updated.status == ReminderStatus.PENDING
    assert updated.next_eligible_check_at is not None
    assert updated.next_eligible_check_at > NOW


async def test_stale_row_is_suppressed_no_provider_call():
    handler, reminder_schedule, preferences, push_provider, suppression, delivery_log = _build()
    entry = make_reminder_entry(
        due_at=NOW - timedelta(hours=5), relevance_expires_at=NOW - timedelta(hours=1)
    )
    reminder_schedule.seed(entry)
    preferences.seed(entry.user_id, "fasting", push_enabled=True)

    await handler.handle(NOW)

    assert len(push_provider.calls) == 0
    updated = await reminder_schedule.get_by_source(entry.source_aggregate_id, "fasting")
    assert updated.status == ReminderStatus.SUPPRESSED
