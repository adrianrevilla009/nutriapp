"""SendNewFollowerPushCommand + handler -- reacts to social-service's
UserFollowed event (/plans/social-service/implementation-plan.md section 6
/ PR A). Dispatches an opt-in, suppressible `new_follower` push
notification to the followee (the user who gained a follower, never the
follower) -- `notification-service` only turns social-service's
already-made decision to notify into a delivery (notification-conventions
SKILL.md), it never decides whether a follow is notify-worthy.

Opt-in only (docs/notifications.md section 2, `PUSH_CATEGORIES` is
suppressible-by-preference): mirrors `ScanAndSendDueRemindersHandler`'s
existing rule that a category with no explicit preference row is treated
the same as an explicit opt-out -- `NotificationPreference`'s
`push_enabled=True` constructor default is a UI default only (surfaced by
`GetNotificationPreferencesHandler`), never sufficient on its own to
authorize a send.

Quiet hours (docs/notifications.md section 2): `new_follower` is
non-transactional, so it is quiet-hours-gated exactly like the
meal/water/fasting reminder categories -- never dropped, never sent
regardless of the window. Unlike those reminders, `UserFollowed` is a
one-shot triggering event with no natural "next occurrence" a periodic
scan can retry against, so a quiet-hours-delayed send is persisted as a
`PendingPushDispatch` row (see domain/entities/pending_push_dispatch.py)
instead, and later picked up by `PendingPushDispatchScanWorker`/
`ScanAndSendPendingPushDispatchesHandler`.

Idempotent by (event_id, channel="push") via
ProcessedNotificationsRepositoryPort, checked first (messaging-conventions
SKILL.md). This covers both paths: an immediate send and a persisted
pending-dispatch row are each marked processed so a redelivered
triggering event never double-sends and never double-persists a pending
row.

Device identity: no device-token registration table exists yet (same
narrow, documented placeholder as scan_and_send_due_reminders.py) -- the
suppression-list check and the push-provider call both use the followee's
user id itself as the device identifier.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import SendNotificationFailedError
from domain.entities.delivery_log_record import DeliveryLogRecord
from domain.entities.pending_push_dispatch import PendingPushDispatch
from domain.ports.delivery_log_repository_port import DeliveryLogRepositoryPort
from domain.ports.pending_push_dispatch_repository_port import (
    PendingPushDispatchRepositoryPort,
)
from domain.ports.preferences_repository_port import PreferencesRepositoryPort
from domain.ports.processed_notifications_repository_port import (
    ProcessedNotificationsRepositoryPort,
)
from domain.ports.push_provider_port import PushProviderPort, PushProviderUnavailableError
from domain.ports.suppression_repository_port import SuppressionRepositoryPort
from domain.ports.template_renderer_port import TemplateRendererPort
from domain.services import quiet_hours_policy
from domain.value_objects.delivery_status import DeliveryStatus
from domain.value_objects.notification_category import Channel
from domain.value_objects.template_id import TemplateId

CHANNEL = "push"
CATEGORY_NAME = "new_follower"
TEMPLATE_ID = TemplateId("new_follower", 1)


@dataclass(frozen=True, slots=True)
class SendNewFollowerPushCommand:
    event_id: uuid.UUID
    follow_id: uuid.UUID
    follower_id: uuid.UUID
    followee_id: uuid.UUID
    followed_at: datetime
    correlation_id: str


class SendNewFollowerPushHandler:
    def __init__(
        self,
        push_provider: PushProviderPort,
        template_renderer: TemplateRendererPort,
        processed_notifications: ProcessedNotificationsRepositoryPort,
        preferences: PreferencesRepositoryPort,
        suppression: SuppressionRepositoryPort,
        delivery_log: DeliveryLogRepositoryPort,
        pending_push_dispatch: PendingPushDispatchRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._push_provider = push_provider
        self._template_renderer = template_renderer
        self._processed = processed_notifications
        self._preferences = preferences
        self._suppression = suppression
        self._delivery_log = delivery_log
        self._pending_push_dispatch = pending_push_dispatch
        self._now_fn = now_fn

    async def handle(self, command: SendNewFollowerPushCommand) -> None:
        if await self._processed.already_processed(command.event_id, CHANNEL):
            return

        preference = await self._preferences.get_category(command.followee_id, CATEGORY_NAME)
        if preference is None or not preference.push_enabled:
            # Opted out (or never explicitly opted in -- opt-in only, see
            # module docstring): no dispatch attempt at all, test-plan
            # section 6's suppressibility case.
            await self._processed.mark_processed(command.event_id, CHANNEL)
            return

        device_identifier = str(command.followee_id)
        if await self._suppression.is_suppressed(
            command.followee_id, Channel.PUSH, device_identifier
        ):
            await self._processed.mark_processed(command.event_id, CHANNEL)
            return

        context = {
            "category": CATEGORY_NAME,
            "follow_id": str(command.follow_id),
            "follower_id": str(command.follower_id),
        }

        now = self._now_fn()
        if preference.quiet_hours.contains(now):
            # Non-transactional -- delayed to the next allowed window, never
            # dropped (docs/notifications.md section 2). One-shot event, no
            # natural "next occurrence" to retry against, so it is persisted
            # here for PendingPushDispatchScanWorker to pick up once due.
            next_allowed = quiet_hours_policy.next_allowed_send_time(
                preference.category, preference.quiet_hours, now
            )
            await self._pending_push_dispatch.add(
                PendingPushDispatch(
                    dispatch_id=uuid.uuid4(),
                    user_id=command.followee_id,
                    category=preference.category,
                    template_id=TEMPLATE_ID,
                    context=context,
                    correlation_id=command.correlation_id,
                    earliest_dispatch_at=next_allowed,
                )
            )
            await self._processed.mark_processed(command.event_id, CHANNEL)
            return

        rendered = self._template_renderer.render_push(TEMPLATE_ID, context)

        try:
            await self._push_provider.send(
                device_token=device_identifier,
                title=rendered.title,
                body=rendered.body,
                data=rendered.data,
                correlation_id=command.correlation_id,
            )
        except PushProviderUnavailableError as exc:
            await self._delivery_log.record(
                DeliveryLogRecord(
                    delivery_id=uuid.uuid4(),
                    user_id=command.followee_id,
                    channel=Channel.PUSH,
                    template_id=TEMPLATE_ID,
                    status=DeliveryStatus.FAILED,
                    attempted_at=self._now_fn(),
                    failure_reason=str(exc),
                )
            )
            raise SendNotificationFailedError(
                "Could not send the new-follower push notification."
            ) from exc

        await self._delivery_log.record(
            DeliveryLogRecord(
                delivery_id=uuid.uuid4(),
                user_id=command.followee_id,
                channel=Channel.PUSH,
                template_id=TEMPLATE_ID,
                status=DeliveryStatus.SENT,
                attempted_at=self._now_fn(),
            )
        )
        await self._processed.mark_processed(command.event_id, CHANNEL)
