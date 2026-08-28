"""UpdateReminderScheduleHandler -- projects diary-service's
FastingWindowStarted/Ended, MealPlanned/Updated/Removed, and
WaterIntakeLogged/Removed events into the local reminder_schedule
read-model projection (implementation plan section 1/9.1's local-
projection-plus-in-service-scheduler design -- never a new synchronous
call into diary-service).

Reminder-lead/relevance-window constants are a deliberate, documented,
narrowly-scoped product choice (not specified further by the approved
plan) -- tunable later without a schema change.

WaterIntakeLogged/Removed are intentionally no-ops here (test-plan
section 1, pinned explicitly): a single water-intake log/removal is not
by itself a reminder trigger -- the water reminder is described in
docs/notifications.md as a "haven't logged in a while" absence signal,
which needs a different mechanism (e.g. a periodic per-user last-logged
check) not specified by the approved plan/test-plan and therefore not
built in this pass; reserved as a documented follow-up.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from domain.entities.reminder_schedule_entry import ReminderScheduleEntry
from domain.ports.reminder_schedule_repository_port import ReminderScheduleRepositoryPort
from domain.value_objects.notification_category import NotificationCategory

# A fasting reminder becomes due once a window has been open this long
# (a typical 16:8 intermittent-fasting cadence), and stays relevant for a
# further grace period after that before being considered stale.
FASTING_REMINDER_LEAD = timedelta(hours=16)
FASTING_REMINDER_RELEVANCE = timedelta(hours=4)

# A meal reminder becomes due this long before the planned time, and
# stays relevant until this long after it.
MEAL_REMINDER_LEAD = timedelta(minutes=30)
MEAL_REMINDER_RELEVANCE = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class FastingWindowStartedCommand:
    event_id: uuid.UUID
    window_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime


@dataclass(frozen=True, slots=True)
class FastingWindowEndedCommand:
    event_id: uuid.UUID
    window_id: uuid.UUID
    user_id: uuid.UUID
    ended_at: datetime


@dataclass(frozen=True, slots=True)
class MealPlannedCommand:
    event_id: uuid.UUID
    plan_entry_id: uuid.UUID
    user_id: uuid.UUID
    planned_for: datetime


@dataclass(frozen=True, slots=True)
class MealPlanUpdatedCommand:
    event_id: uuid.UUID
    plan_entry_id: uuid.UUID
    user_id: uuid.UUID
    planned_for: datetime


@dataclass(frozen=True, slots=True)
class MealPlanRemovedCommand:
    event_id: uuid.UUID
    plan_entry_id: uuid.UUID
    user_id: uuid.UUID
    removed_at: datetime


@dataclass(frozen=True, slots=True)
class WaterIntakeLoggedCommand:
    event_id: uuid.UUID
    intake_id: uuid.UUID
    user_id: uuid.UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class WaterIntakeRemovedCommand:
    event_id: uuid.UUID
    intake_id: uuid.UUID
    user_id: uuid.UUID
    removed_at: datetime


class UpdateReminderScheduleHandler:
    def __init__(self, reminder_schedule: ReminderScheduleRepositoryPort) -> None:
        self._reminder_schedule = reminder_schedule

    async def handle_fasting_window_started(self, command: FastingWindowStartedCommand) -> None:
        due_at = command.started_at + FASTING_REMINDER_LEAD
        entry = ReminderScheduleEntry(
            schedule_id=uuid.uuid4(),
            user_id=command.user_id,
            category=NotificationCategory.push("fasting"),
            source_aggregate_id=str(command.window_id),
            due_at=due_at,
            relevance_expires_at=due_at + FASTING_REMINDER_RELEVANCE,
        )
        await self._reminder_schedule.upsert(entry)

    async def handle_fasting_window_ended(self, command: FastingWindowEndedCommand) -> None:
        await self._reminder_schedule.remove_by_source(str(command.window_id), "fasting")

    async def handle_meal_planned(self, command: MealPlannedCommand) -> None:
        due_at = command.planned_for - MEAL_REMINDER_LEAD
        entry = ReminderScheduleEntry(
            schedule_id=uuid.uuid4(),
            user_id=command.user_id,
            category=NotificationCategory.push("meal"),
            source_aggregate_id=str(command.plan_entry_id),
            due_at=due_at,
            relevance_expires_at=command.planned_for + MEAL_REMINDER_RELEVANCE,
        )
        await self._reminder_schedule.upsert(entry)

    async def handle_meal_plan_updated(self, command: MealPlanUpdatedCommand) -> None:
        due_at = command.planned_for - MEAL_REMINDER_LEAD
        entry = ReminderScheduleEntry(
            schedule_id=uuid.uuid4(),
            user_id=command.user_id,
            category=NotificationCategory.push("meal"),
            source_aggregate_id=str(command.plan_entry_id),
            due_at=due_at,
            relevance_expires_at=command.planned_for + MEAL_REMINDER_RELEVANCE,
        )
        # upsert is keyed by (source_aggregate_id, category) at the
        # repository level -- this updates the existing row in place,
        # never inserts a duplicate (test-plan section 1).
        await self._reminder_schedule.upsert(entry)

    async def handle_meal_plan_removed(self, command: MealPlanRemovedCommand) -> None:
        await self._reminder_schedule.remove_by_source(str(command.plan_entry_id), "meal")

    async def handle_water_intake_logged(self, command: WaterIntakeLoggedCommand) -> None:
        return None

    async def handle_water_intake_removed(self, command: WaterIntakeRemovedCommand) -> None:
        return None
