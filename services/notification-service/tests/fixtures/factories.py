"""Fake ports for unit tests (testing-strategy SKILL.md). Mirrors
food-recognition-service's tests/fixtures/factories.py precedent."""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Any

from domain.entities.notification_preference import NotificationPreference
from domain.entities.pending_push_dispatch import PendingPushDispatch
from domain.entities.reminder_schedule_entry import ReminderScheduleEntry
from domain.ports.email_provider_port import EmailSendResult
from domain.ports.push_provider_port import PushSendResult
from domain.ports.template_renderer_port import RenderedEmail, RenderedPush
from domain.ports.token_reveal_port import RevealedToken
from domain.value_objects.notification_category import Channel, NotificationCategory
from domain.value_objects.pending_dispatch_status import PendingDispatchStatus
from domain.value_objects.quiet_hours_window import QuietHoursWindow
from domain.value_objects.reminder_status import ReminderStatus
from domain.value_objects.template_id import TemplateId


class FakeTokenRevealPort:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.result: RevealedToken | None = RevealedToken(
            secret="raw-secret", user_id=uuid.uuid4(), kind="email_verification"
        )
        self.error_to_raise: Exception | None = None

    async def reveal(self, reference_id: str) -> RevealedToken:
        self.calls.append(reference_id)
        if self.error_to_raise is not None:
            raise self.error_to_raise
        assert self.result is not None
        return self.result


class FakeEmailProviderPort:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error_to_raise: Exception | None = None

    async def send(
        self, *, to: str, subject: str, html_body: str, correlation_id: str
    ) -> EmailSendResult:
        self.calls.append(
            {"to": to, "subject": subject, "html_body": html_body, "correlation_id": correlation_id}
        )
        if self.error_to_raise is not None:
            raise self.error_to_raise
        return EmailSendResult(provider_message_id="fake-email-id")


class FakePushProviderPort:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error_to_raise: Exception | None = None

    async def send(
        self, *, device_token: str, title: str, body: str, data: dict[str, str], correlation_id: str
    ) -> PushSendResult:
        self.calls.append(
            {
                "device_token": device_token,
                "title": title,
                "body": body,
                "data": data,
                "correlation_id": correlation_id,
            }
        )
        if self.error_to_raise is not None:
            raise self.error_to_raise
        return PushSendResult(provider_message_id="fake-push-id")


class FakeProcessedNotificationsRepositoryPort:
    def __init__(self) -> None:
        self._processed: set[tuple[uuid.UUID, str]] = set()

    async def already_processed(self, event_id: uuid.UUID, channel: str) -> bool:
        return (event_id, channel) in self._processed

    async def mark_processed(self, event_id: uuid.UUID, channel: str) -> None:
        self._processed.add((event_id, channel))


class FakeDeliveryLogRepositoryPort:
    def __init__(self) -> None:
        self.records: list[Any] = []

    async def record(self, entry: Any) -> None:
        self.records.append(entry)


class FakeSuppressionRepositoryPort:
    def __init__(self) -> None:
        self._suppressed: set[tuple[uuid.UUID, Channel, str]] = set()
        self.added: list[tuple[uuid.UUID, Channel, str, Any]] = []

    async def is_suppressed(
        self, user_id: uuid.UUID, channel: Channel, address_or_device: str
    ) -> bool:
        return (user_id, channel, address_or_device) in self._suppressed

    async def add(
        self, user_id: uuid.UUID, channel: Channel, address_or_device: str, reason: Any
    ) -> None:
        self._suppressed.add((user_id, channel, address_or_device))
        self.added.append((user_id, channel, address_or_device, reason))

    def seed_suppressed(self, user_id: uuid.UUID, channel: Channel, address_or_device: str) -> None:
        self._suppressed.add((user_id, channel, address_or_device))


class FakePreferencesRepositoryPort:
    def __init__(self) -> None:
        self._by_key: dict[tuple[uuid.UUID, str], NotificationPreference] = {}

    async def get_all(self, user_id: uuid.UUID) -> list[NotificationPreference]:
        return [pref for (uid, _cat), pref in self._by_key.items() if uid == user_id]

    async def get_category(
        self, user_id: uuid.UUID, category_name: str
    ) -> NotificationPreference | None:
        return self._by_key.get((user_id, category_name))

    async def upsert(self, preference: NotificationPreference) -> None:
        self._by_key[(preference.user_id, preference.category.name)] = preference

    def seed(
        self,
        user_id: uuid.UUID,
        category_name: str,
        push_enabled: bool = True,
        quiet_hours: QuietHoursWindow | None = None,
    ) -> NotificationPreference:
        preference = NotificationPreference(
            user_id=user_id,
            category=NotificationCategory.push(category_name),
            push_enabled=push_enabled,
            quiet_hours=quiet_hours
            or QuietHoursWindow(start=time(22, 0), end=time(8, 0), tz="UTC"),
        )
        self._by_key[(user_id, category_name)] = preference
        return preference


class FakeReminderScheduleRepositoryPort:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, ReminderScheduleEntry] = {}
        self._by_source: dict[tuple[str, str], uuid.UUID] = {}

    async def upsert(self, entry: ReminderScheduleEntry) -> None:
        key = (entry.source_aggregate_id, entry.category.name)
        existing_id = self._by_source.get(key)
        if existing_id is not None:
            entry.schedule_id = existing_id
        self._by_source[key] = entry.schedule_id
        self._by_id[entry.schedule_id] = entry

    async def get_by_source(
        self, source_aggregate_id: str, category_name: str
    ) -> ReminderScheduleEntry | None:
        schedule_id = self._by_source.get((source_aggregate_id, category_name))
        return None if schedule_id is None else self._by_id.get(schedule_id)

    async def remove_by_source(self, source_aggregate_id: str, category_name: str) -> None:
        schedule_id = self._by_source.pop((source_aggregate_id, category_name), None)
        if schedule_id is not None:
            self._by_id.pop(schedule_id, None)

    async def list_pending(self, now: datetime) -> list[ReminderScheduleEntry]:
        return [
            entry
            for entry in self._by_id.values()
            if entry.status == ReminderStatus.PENDING
            and (entry.next_eligible_check_at is None or entry.next_eligible_check_at <= now)
        ]

    async def mark_status(
        self,
        schedule_id: uuid.UUID,
        status: ReminderStatus,
        next_eligible_check_at: datetime | None = None,
    ) -> None:
        entry = self._by_id[schedule_id]
        entry.status = status
        entry.next_eligible_check_at = next_eligible_check_at

    def seed(self, entry: ReminderScheduleEntry) -> None:
        self._by_source[(entry.source_aggregate_id, entry.category.name)] = entry.schedule_id
        self._by_id[entry.schedule_id] = entry


class FakeTemplateRendererPort:
    def __init__(self) -> None:
        self.email_calls: list[tuple[Any, Any]] = []
        self.push_calls: list[tuple[Any, Any]] = []

    def render_email(self, template_id: Any, context: Any) -> RenderedEmail:
        self.email_calls.append((template_id, context))
        return RenderedEmail(subject=f"subject-{template_id.name}", html_body=f"body-{context}")

    def render_push(self, template_id: Any, context: Any) -> RenderedPush:
        self.push_calls.append((template_id, context))
        return RenderedPush(title=f"title-{template_id.name}", body="body", data={})


class FakePendingPushDispatchRepositoryPort:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, PendingPushDispatch] = {}
        self.added: list[PendingPushDispatch] = []

    async def add(self, dispatch: PendingPushDispatch) -> None:
        self._by_id[dispatch.dispatch_id] = dispatch
        self.added.append(dispatch)

    async def list_due(self, now: datetime) -> list[PendingPushDispatch]:
        return [
            dispatch
            for dispatch in self._by_id.values()
            if dispatch.status == PendingDispatchStatus.PENDING
            and dispatch.earliest_dispatch_at <= now
        ]

    async def mark_status(
        self,
        dispatch_id: uuid.UUID,
        status: PendingDispatchStatus,
        earliest_dispatch_at: datetime | None = None,
    ) -> None:
        dispatch = self._by_id[dispatch_id]
        dispatch.status = status
        if earliest_dispatch_at is not None:
            dispatch.earliest_dispatch_at = earliest_dispatch_at

    def seed(self, dispatch: PendingPushDispatch) -> None:
        self._by_id[dispatch.dispatch_id] = dispatch


def make_pending_push_dispatch(
    *,
    user_id: uuid.UUID | None = None,
    category_name: str = "new_follower",
    template_name: str = "new_follower",
    template_version: int = 1,
    context: dict[str, str] | None = None,
    correlation_id: str = "corr-1",
    earliest_dispatch_at: datetime,
    status: PendingDispatchStatus = PendingDispatchStatus.PENDING,
) -> PendingPushDispatch:
    return PendingPushDispatch(
        dispatch_id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        category=NotificationCategory.push(category_name),
        template_id=TemplateId(template_name, template_version),
        context=context or {},
        correlation_id=correlation_id,
        earliest_dispatch_at=earliest_dispatch_at,
        status=status,
    )


def make_reminder_entry(
    *,
    user_id: uuid.UUID | None = None,
    category_name: str = "fasting",
    source_aggregate_id: str | None = None,
    due_at: datetime,
    relevance_expires_at: datetime,
    status: ReminderStatus = ReminderStatus.PENDING,
    next_eligible_check_at: datetime | None = None,
) -> ReminderScheduleEntry:
    return ReminderScheduleEntry(
        schedule_id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        category=NotificationCategory.push(category_name),
        source_aggregate_id=source_aggregate_id or str(uuid.uuid4()),
        due_at=due_at,
        relevance_expires_at=relevance_expires_at,
        status=status,
        next_eligible_check_at=next_eligible_check_at,
    )
