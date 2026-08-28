"""ScanAndSendDueRemindersHandler -- the periodic in-service worker use
case (implementation plan section 1/9.1): scans the reminder_schedule
projection, applies the domain-layer due/stale + quiet-hours rules,
honors per-category preference and the suppression list, and enqueues a
push send for anything due.

Device identity: no device-token registration table exists yet in this
plan's scope (implementation plan section 9.3 -- device registration is a
stub-only feature until a mobile client exists). The suppression-list and
push-provider calls below use the user id itself as the device
identifier, a narrow, documented placeholder that keeps the suppression
check and provider call shape stable and swaps cleanly for a real device
token once `POST /api/v1/notifications/devices` grows real persistence.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from domain.entities.delivery_log_record import DeliveryLogRecord
from domain.ports.delivery_log_repository_port import DeliveryLogRepositoryPort
from domain.ports.preferences_repository_port import PreferencesRepositoryPort
from domain.ports.push_provider_port import PushProviderPort, PushProviderUnavailableError
from domain.ports.reminder_schedule_repository_port import ReminderScheduleRepositoryPort
from domain.ports.suppression_repository_port import SuppressionRepositoryPort
from domain.ports.template_renderer_port import TemplateRendererPort
from domain.services import due_and_stale_policy, quiet_hours_policy
from domain.value_objects.delivery_status import DeliveryStatus
from domain.value_objects.notification_category import Channel
from domain.value_objects.reminder_status import ReminderStatus
from domain.value_objects.template_id import TemplateId

_TEMPLATE_NAME_BY_CATEGORY = {
    "fasting": "fasting_reminder",
    "meal": "meal_reminder",
    "water": "water_reminder",
}


class ScanAndSendDueRemindersHandler:
    def __init__(
        self,
        reminder_schedule: ReminderScheduleRepositoryPort,
        preferences: PreferencesRepositoryPort,
        push_provider: PushProviderPort,
        suppression: SuppressionRepositoryPort,
        template_renderer: TemplateRendererPort,
        delivery_log: DeliveryLogRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._reminder_schedule = reminder_schedule
        self._preferences = preferences
        self._push_provider = push_provider
        self._suppression = suppression
        self._template_renderer = template_renderer
        self._delivery_log = delivery_log
        self._now_fn = now_fn

    async def handle(self, now: datetime | None = None) -> None:
        now = now or self._now_fn()
        for entry in await self._reminder_schedule.list_pending(now):
            evaluation = due_and_stale_policy.evaluate(
                entry.due_at, entry.relevance_expires_at, now
            )

            if evaluation is due_and_stale_policy.ReminderEvaluation.NOT_DUE:
                continue

            if evaluation is due_and_stale_policy.ReminderEvaluation.STALE:
                await self._reminder_schedule.mark_status(
                    entry.schedule_id, ReminderStatus.SUPPRESSED
                )
                continue

            preference = await self._preferences.get_category(entry.user_id, entry.category.name)
            if preference is None or not preference.push_enabled:
                await self._reminder_schedule.mark_status(
                    entry.schedule_id, ReminderStatus.SUPPRESSED
                )
                continue

            device_identifier = str(entry.user_id)
            if await self._suppression.is_suppressed(
                entry.user_id, Channel.PUSH, device_identifier
            ):
                await self._reminder_schedule.mark_status(
                    entry.schedule_id, ReminderStatus.SUPPRESSED
                )
                continue

            if preference.quiet_hours.contains(now):
                next_check = quiet_hours_policy.next_allowed_send_time(
                    entry.category, preference.quiet_hours, now
                )
                await self._reminder_schedule.mark_status(
                    entry.schedule_id, ReminderStatus.PENDING, next_eligible_check_at=next_check
                )
                continue

            template_id = TemplateId(_TEMPLATE_NAME_BY_CATEGORY[entry.category.name], 1)
            rendered = self._template_renderer.render_push(
                template_id,
                {"category": entry.category.name, "source_aggregate_id": entry.source_aggregate_id},
            )

            try:
                await self._push_provider.send(
                    device_token=device_identifier,
                    title=rendered.title,
                    body=rendered.body,
                    data=rendered.data,
                    correlation_id=str(entry.schedule_id),
                )
            except PushProviderUnavailableError as exc:
                await self._delivery_log.record(
                    DeliveryLogRecord(
                        delivery_id=entry.schedule_id,
                        user_id=entry.user_id,
                        channel=Channel.PUSH,
                        template_id=template_id,
                        status=DeliveryStatus.FAILED,
                        attempted_at=now,
                        failure_reason=str(exc),
                    )
                )
                # Left pending: the next scan tick retries, same as a
                # quiet-hours delay -- a transient provider failure must
                # not silently suppress a not-yet-stale reminder.
                continue

            await self._delivery_log.record(
                DeliveryLogRecord(
                    delivery_id=entry.schedule_id,
                    user_id=entry.user_id,
                    channel=Channel.PUSH,
                    template_id=template_id,
                    status=DeliveryStatus.SENT,
                    attempted_at=now,
                )
            )
            await self._reminder_schedule.mark_status(entry.schedule_id, ReminderStatus.SENT)
