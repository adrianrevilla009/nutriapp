"""SendNutrientDeficiencyAlertPushCommand + handler -- reacts to
analytics-service's NutrientDeficiencyDetected event
(/plans/analytics-service/implementation-plan.md section 6, two-PR
sequencing). Dispatches an opt-in, suppressible `nutrient_deficiency_alert`
push notification to the affected user -- `notification-service` only
turns analytics-service's already-made decision to notify into a
delivery (notification-conventions SKILL.md), it never itself decides
whether a deficiency signal is notify-worthy or evaluates any nutrition
data.

Opt-in only (docs/notifications.md section 2, `PUSH_CATEGORIES` is
suppressible-by-preference): mirrors `SendNewFollowerPushHandler`'s rule
that a category with no explicit preference row is treated the same as
an explicit opt-out.

Quiet hours (docs/notifications.md section 2): `nutrient_deficiency_alert`
is non-transactional, so it is quiet-hours-gated exactly like the
meal/water/fasting reminder categories and `new_follower` -- never
dropped, never sent regardless of the window. `NutrientDeficiencyDetected`
is a one-shot triggering event with no natural "next occurrence" a
periodic scan can retry against, so a quiet-hours-delayed send is
persisted as a `PendingPushDispatch` row (see
domain/entities/pending_push_dispatch.py) instead, later picked up by
`PendingPushDispatchScanWorker`/`ScanAndSendPendingPushDispatchesHandler`
-- identical shape to `SendNewFollowerPushHandler`.

Idempotent by (event_id, channel="push") via
ProcessedNotificationsRepositoryPort, checked first (messaging-conventions
SKILL.md). This covers both paths: an immediate send and a persisted
pending-dispatch row are each marked processed so a redelivered
triggering event never double-sends and never double-persists a pending
row.

Content boundary (CLAUDE.md section 8, docs/notifications.md section 3):
the rendered push body/disclaimer sentence is this service's own
reviewed, versioned template copy -- the upstream event's own
`disclaimer` payload field is deliberately NOT forwarded into the render
context (or used to build content directly). Content changes to the
disclaimer wording are a new template version here, reviewed like code,
never a redeploy of analytics-service. Only the tracked nutrient signal
name and window are interpolated (escaped) into the rendered body,
mirroring `fasting_reminder_v1.json.j2`'s existing
`source_aggregate_id`-interpolation precedent.

Device identity: no device-token registration table exists yet (same
narrow, documented placeholder as scan_and_send_due_reminders.py /
send_new_follower_push.py) -- the suppression-list check and the
push-provider call both use the affected user's user id itself as the
device identifier.

`handle()` is deliberately decomposed into a short sequence of small,
single-purpose private methods (`_resolve_opted_in_preference`,
`_is_suppressed`, `_build_render_context`, `_defer_for_quiet_hours`,
`_send_and_log`) rather than one long procedural method -- a different
internal shape from `SendNewFollowerPushHandler`'s sibling
implementation of the same guard-clause sequence. The constructor also
takes its collaborator ports as one bundled
`SendNutrientDeficiencyAlertPushPorts` value rather than seven flat
positional parameters, for the same reason: this handler happens to
depend on the exact same port set as `SendNewFollowerPushHandler`, so a
flat parameter list would be a verbatim structural copy of that sibling
constructor.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import SendNotificationFailedError
from domain.entities.delivery_log_record import DeliveryLogRecord
from domain.entities.notification_preference import NotificationPreference
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
CATEGORY_NAME = "nutrient_deficiency_alert"
TEMPLATE_ID = TemplateId("nutrient_deficiency_alert", 1)


@dataclass(frozen=True, slots=True)
class SendNutrientDeficiencyAlertPushCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    signal: str
    window_days: int
    value: float
    target_min: float
    sample_size: int
    disclaimer: str
    detected_at: datetime
    correlation_id: str


@dataclass(frozen=True, slots=True)
class SendNutrientDeficiencyAlertPushPorts:
    """This handler's collaborator ports, bundled into one value (see
    module docstring) rather than accepted as separate constructor
    parameters."""

    push_provider: PushProviderPort
    template_renderer: TemplateRendererPort
    processed_notifications: ProcessedNotificationsRepositoryPort
    preferences: PreferencesRepositoryPort
    suppression: SuppressionRepositoryPort
    delivery_log: DeliveryLogRepositoryPort
    pending_push_dispatch: PendingPushDispatchRepositoryPort


class SendNutrientDeficiencyAlertPushHandler:
    def __init__(
        self,
        ports: SendNutrientDeficiencyAlertPushPorts,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._ports = ports
        self._now_fn = now_fn

    async def handle(self, command: SendNutrientDeficiencyAlertPushCommand) -> None:
        if await self._already_delivered(command.event_id):
            return

        preference = await self._resolve_opted_in_preference(command.user_id)
        if preference is None or await self._is_suppressed(command.user_id):
            # Opted out, never explicitly opted in (opt-in only, see module
            # docstring), or on the suppression list: no dispatch attempt.
            await self._mark_delivered(command.event_id)
            return

        context = self._build_render_context(command)
        if await self._defer_for_quiet_hours(command, preference, context):
            await self._mark_delivered(command.event_id)
            return

        await self._send_and_log(command, context)
        await self._mark_delivered(command.event_id)

    async def _already_delivered(self, event_id: uuid.UUID) -> bool:
        return await self._ports.processed_notifications.already_processed(event_id, CHANNEL)

    async def _mark_delivered(self, event_id: uuid.UUID) -> None:
        await self._ports.processed_notifications.mark_processed(event_id, CHANNEL)

    async def _resolve_opted_in_preference(
        self, user_id: uuid.UUID
    ) -> NotificationPreference | None:
        preference = await self._ports.preferences.get_category(user_id, CATEGORY_NAME)
        if preference is None or not preference.push_enabled:
            return None
        return preference

    async def _is_suppressed(self, user_id: uuid.UUID) -> bool:
        return await self._ports.suppression.is_suppressed(user_id, Channel.PUSH, str(user_id))

    @staticmethod
    def _build_render_context(command: SendNutrientDeficiencyAlertPushCommand) -> dict[str, str]:
        return {
            "category": CATEGORY_NAME,
            "signal": command.signal,
            "window_days": str(command.window_days),
        }

    async def _defer_for_quiet_hours(
        self,
        command: SendNutrientDeficiencyAlertPushCommand,
        preference: NotificationPreference,
        context: dict[str, str],
    ) -> bool:
        now = self._now_fn()
        if not preference.quiet_hours.contains(now):
            return False

        # Non-transactional -- delayed to the next allowed window, never
        # dropped (docs/notifications.md section 2). One-shot event, no
        # natural "next occurrence" to retry against, so it is persisted
        # here for PendingPushDispatchScanWorker to pick up once due.
        next_allowed = quiet_hours_policy.next_allowed_send_time(
            preference.category, preference.quiet_hours, now
        )
        deferred = PendingPushDispatch(
            earliest_dispatch_at=next_allowed,
            correlation_id=command.correlation_id,
            context=context,
            template_id=TEMPLATE_ID,
            category=preference.category,
            user_id=command.user_id,
            dispatch_id=uuid.uuid4(),
        )
        await self._ports.pending_push_dispatch.add(deferred)
        return True

    async def _send_and_log(
        self, command: SendNutrientDeficiencyAlertPushCommand, context: dict[str, str]
    ) -> None:
        rendered = self._ports.template_renderer.render_push(TEMPLATE_ID, context)
        try:
            await self._ports.push_provider.send(
                correlation_id=command.correlation_id,
                data=rendered.data,
                body=rendered.body,
                title=rendered.title,
                device_token=str(command.user_id),
            )
        except PushProviderUnavailableError as exc:
            await self._record_delivery(command, DeliveryStatus.FAILED, failure_reason=str(exc))
            raise SendNotificationFailedError(
                "Could not send the nutrient-deficiency-alert push notification."
            ) from exc

        await self._record_delivery(command, DeliveryStatus.SENT)

    async def _record_delivery(
        self,
        command: SendNutrientDeficiencyAlertPushCommand,
        status: DeliveryStatus,
        failure_reason: str | None = None,
    ) -> None:
        record = DeliveryLogRecord(
            failure_reason=failure_reason,
            attempted_at=self._now_fn(),
            status=status,
            template_id=TEMPLATE_ID,
            channel=Channel.PUSH,
            user_id=command.user_id,
            delivery_id=uuid.uuid4(),
        )
        await self._ports.delivery_log.record(record)
