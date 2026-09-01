"""ScanAndSendPendingPushDispatchesHandler -- the periodic in-service
worker use case for `pending_push_dispatch` rows (see
domain/entities/pending_push_dispatch.py's module docstring for why this
is a separate mechanism from `ScanAndSendDueRemindersHandler`/
`reminder_schedule`). Re-checks preference/suppression at dispatch time
(not just at the moment the row was persisted) -- the same guarantee
`ScanAndSendDueRemindersHandler` gives reminders: a user who opts out or
gets suppressed between the original event and this scan tick must not
receive a stale send. If quiet hours are, unusually, still active at scan
time (e.g. a delayed scan tick, or a preference change since the row was
persisted), the row is rescheduled to the next allowed window rather than
sent -- never sent inside quiet hours, never dropped.

Device identity: same narrow, documented placeholder as
scan_and_send_due_reminders.py/send_new_follower_push.py -- the recipient
user id itself is used as the device identifier.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from domain.entities.delivery_log_record import DeliveryLogRecord
from domain.ports.delivery_log_repository_port import DeliveryLogRepositoryPort
from domain.ports.pending_push_dispatch_repository_port import (
    PendingPushDispatchRepositoryPort,
)
from domain.ports.preferences_repository_port import PreferencesRepositoryPort
from domain.ports.push_provider_port import PushProviderPort, PushProviderUnavailableError
from domain.ports.suppression_repository_port import SuppressionRepositoryPort
from domain.ports.template_renderer_port import TemplateRendererPort
from domain.services import quiet_hours_policy
from domain.value_objects.delivery_status import DeliveryStatus
from domain.value_objects.notification_category import Channel
from domain.value_objects.pending_dispatch_status import PendingDispatchStatus


class ScanAndSendPendingPushDispatchesHandler:
    def __init__(
        self,
        pending_push_dispatch: PendingPushDispatchRepositoryPort,
        preferences: PreferencesRepositoryPort,
        push_provider: PushProviderPort,
        suppression: SuppressionRepositoryPort,
        template_renderer: TemplateRendererPort,
        delivery_log: DeliveryLogRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._pending_push_dispatch = pending_push_dispatch
        self._preferences = preferences
        self._push_provider = push_provider
        self._suppression = suppression
        self._template_renderer = template_renderer
        self._delivery_log = delivery_log
        self._now_fn = now_fn

    async def handle(self, now: datetime | None = None) -> None:
        now = now or self._now_fn()
        for dispatch in await self._pending_push_dispatch.list_due(now):
            preference = await self._preferences.get_category(
                dispatch.user_id, dispatch.category.name
            )
            if preference is None or not preference.push_enabled:
                await self._pending_push_dispatch.mark_status(
                    dispatch.dispatch_id, PendingDispatchStatus.SUPPRESSED
                )
                continue

            device_identifier = str(dispatch.user_id)
            if await self._suppression.is_suppressed(
                dispatch.user_id, Channel.PUSH, device_identifier
            ):
                await self._pending_push_dispatch.mark_status(
                    dispatch.dispatch_id, PendingDispatchStatus.SUPPRESSED
                )
                continue

            if preference.quiet_hours.contains(now):
                next_allowed = quiet_hours_policy.next_allowed_send_time(
                    dispatch.category, preference.quiet_hours, now
                )
                await self._pending_push_dispatch.mark_status(
                    dispatch.dispatch_id,
                    PendingDispatchStatus.PENDING,
                    earliest_dispatch_at=next_allowed,
                )
                continue

            rendered = self._template_renderer.render_push(dispatch.template_id, dispatch.context)

            try:
                await self._push_provider.send(
                    device_token=device_identifier,
                    title=rendered.title,
                    body=rendered.body,
                    data=rendered.data,
                    correlation_id=dispatch.correlation_id,
                )
            except PushProviderUnavailableError as exc:
                await self._delivery_log.record(
                    DeliveryLogRecord(
                        delivery_id=dispatch.dispatch_id,
                        user_id=dispatch.user_id,
                        channel=Channel.PUSH,
                        template_id=dispatch.template_id,
                        status=DeliveryStatus.FAILED,
                        attempted_at=now,
                        failure_reason=str(exc),
                    )
                )
                # Left pending: the next scan tick retries, same as a
                # quiet-hours delay -- a transient provider failure must
                # not silently drop a one-shot pending dispatch.
                continue

            await self._delivery_log.record(
                DeliveryLogRecord(
                    delivery_id=dispatch.dispatch_id,
                    user_id=dispatch.user_id,
                    channel=Channel.PUSH,
                    template_id=dispatch.template_id,
                    status=DeliveryStatus.SENT,
                    attempted_at=now,
                )
            )
            await self._pending_push_dispatch.mark_status(
                dispatch.dispatch_id, PendingDispatchStatus.SENT
            )
