"""UpdateReminderScheduleHandler -- test-plan section 1."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from application.commands.update_reminder_schedule import (
    FastingWindowEndedCommand,
    FastingWindowStartedCommand,
    MealPlannedCommand,
    MealPlanRemovedCommand,
    MealPlanUpdatedCommand,
    UpdateReminderScheduleHandler,
    WaterIntakeLoggedCommand,
    WaterIntakeRemovedCommand,
)
from tests.fixtures.factories import FakeReminderScheduleRepositoryPort

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


async def test_fasting_window_started_creates_reminder_row():
    repo = FakeReminderScheduleRepositoryPort()
    handler = UpdateReminderScheduleHandler(repo)
    window_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await handler.handle_fasting_window_started(
        FastingWindowStartedCommand(
            event_id=uuid.uuid4(), window_id=window_id, user_id=user_id, started_at=NOW
        )
    )

    entry = await repo.get_by_source(str(window_id), "fasting")
    assert entry is not None
    assert entry.user_id == user_id
    assert entry.due_at > NOW
    assert entry.relevance_expires_at > entry.due_at


async def test_fasting_window_ended_removes_matching_row():
    repo = FakeReminderScheduleRepositoryPort()
    handler = UpdateReminderScheduleHandler(repo)
    window_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await handler.handle_fasting_window_started(
        FastingWindowStartedCommand(
            event_id=uuid.uuid4(), window_id=window_id, user_id=user_id, started_at=NOW
        )
    )
    await handler.handle_fasting_window_ended(
        FastingWindowEndedCommand(
            event_id=uuid.uuid4(), window_id=window_id, user_id=user_id, ended_at=NOW
        )
    )

    assert await repo.get_by_source(str(window_id), "fasting") is None


async def test_meal_planned_creates_row_keyed_to_planned_for():
    repo = FakeReminderScheduleRepositoryPort()
    handler = UpdateReminderScheduleHandler(repo)
    plan_entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    planned_for = NOW + timedelta(hours=3)

    await handler.handle_meal_planned(
        MealPlannedCommand(
            event_id=uuid.uuid4(),
            plan_entry_id=plan_entry_id,
            user_id=user_id,
            planned_for=planned_for,
        )
    )

    entry = await repo.get_by_source(str(plan_entry_id), "meal")
    assert entry is not None
    assert entry.due_at < planned_for
    assert entry.relevance_expires_at > planned_for


async def test_meal_plan_updated_updates_existing_row_in_place():
    repo = FakeReminderScheduleRepositoryPort()
    handler = UpdateReminderScheduleHandler(repo)
    plan_entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    original_planned_for = NOW + timedelta(hours=3)
    updated_planned_for = NOW + timedelta(hours=6)

    await handler.handle_meal_planned(
        MealPlannedCommand(
            event_id=uuid.uuid4(),
            plan_entry_id=plan_entry_id,
            user_id=user_id,
            planned_for=original_planned_for,
        )
    )
    original_schedule_id = (await repo.get_by_source(str(plan_entry_id), "meal")).schedule_id

    await handler.handle_meal_plan_updated(
        MealPlanUpdatedCommand(
            event_id=uuid.uuid4(),
            plan_entry_id=plan_entry_id,
            user_id=user_id,
            planned_for=updated_planned_for,
        )
    )

    entry = await repo.get_by_source(str(plan_entry_id), "meal")
    assert entry.schedule_id == original_schedule_id  # updated in place, not duplicated
    assert entry.relevance_expires_at > updated_planned_for


async def test_meal_plan_removed_removes_row():
    repo = FakeReminderScheduleRepositoryPort()
    handler = UpdateReminderScheduleHandler(repo)
    plan_entry_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await handler.handle_meal_planned(
        MealPlannedCommand(
            event_id=uuid.uuid4(),
            plan_entry_id=plan_entry_id,
            user_id=user_id,
            planned_for=NOW + timedelta(hours=3),
        )
    )
    await handler.handle_meal_plan_removed(
        MealPlanRemovedCommand(
            event_id=uuid.uuid4(), plan_entry_id=plan_entry_id, user_id=user_id, removed_at=NOW
        )
    )

    assert await repo.get_by_source(str(plan_entry_id), "meal") is None


async def test_water_intake_logged_does_not_create_a_row():
    repo = FakeReminderScheduleRepositoryPort()
    handler = UpdateReminderScheduleHandler(repo)
    intake_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await handler.handle_water_intake_logged(
        WaterIntakeLoggedCommand(
            event_id=uuid.uuid4(), intake_id=intake_id, user_id=user_id, occurred_at=NOW
        )
    )

    assert await repo.get_by_source(str(intake_id), "water") is None
    assert repo._by_id == {}


async def test_water_intake_removed_does_not_create_a_row():
    # Sibling no-op to WaterIntakeLogged above (test-plan section 1):
    # removing a water-intake entry is likewise not itself a reminder
    # trigger -- pinned explicitly, same rationale as the Logged case.
    repo = FakeReminderScheduleRepositoryPort()
    handler = UpdateReminderScheduleHandler(repo)
    intake_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await handler.handle_water_intake_removed(
        WaterIntakeRemovedCommand(
            event_id=uuid.uuid4(), intake_id=intake_id, user_id=user_id, removed_at=NOW
        )
    )

    assert await repo.get_by_source(str(intake_id), "water") is None
    assert repo._by_id == {}


async def test_applying_same_fasting_started_event_twice_is_idempotent():
    repo = FakeReminderScheduleRepositoryPort()
    handler = UpdateReminderScheduleHandler(repo)
    window_id = uuid.uuid4()
    user_id = uuid.uuid4()
    command = FastingWindowStartedCommand(
        event_id=uuid.uuid4(), window_id=window_id, user_id=user_id, started_at=NOW
    )

    await handler.handle_fasting_window_started(command)
    first = await repo.get_by_source(str(window_id), "fasting")

    await handler.handle_fasting_window_started(command)
    second = await repo.get_by_source(str(window_id), "fasting")

    assert first.schedule_id == second.schedule_id
    assert len(repo._by_id) == 1
