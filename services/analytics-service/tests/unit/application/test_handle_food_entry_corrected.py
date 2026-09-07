from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from application.commands.handle_food_entry_corrected import (
    HandleFoodEntryCorrectedCommand,
    HandleFoodEntryCorrectedHandler,
)
from application.commands.handle_food_entry_logged import (
    HandleFoodEntryLoggedCommand,
    HandleFoodEntryLoggedHandler,
)
from tests.fixtures.factories import (
    FakeDailyLogSummaryRepository,
    FakeProcessedDiaryEventsRepository,
)

OCCURRED_AT = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)


async def test_correction_replaces_not_adds_to_the_original_contribution():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    entry_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await HandleFoodEntryLoggedHandler(processed, summary).handle(
        HandleFoodEntryLoggedCommand(
            event_id=uuid.uuid4(),
            entry_id=entry_id,
            user_id=user_id,
            quantity=1.0,
            calories_kcal_per_unit=500.0,
            protein_g_per_unit=30.0,
            carbs_g_per_unit=40.0,
            fat_g_per_unit=10.0,
            occurred_at=OCCURRED_AT,
        )
    )

    await HandleFoodEntryCorrectedHandler(processed, summary).handle(
        HandleFoodEntryCorrectedCommand(
            event_id=uuid.uuid4(),
            entry_id=entry_id,
            user_id=user_id,
            quantity=1.0,
            calories_kcal_per_unit=300.0,
            protein_g_per_unit=20.0,
            carbs_g_per_unit=25.0,
            fat_g_per_unit=5.0,
            occurred_at=OCCURRED_AT,
        )
    )

    day = summary.days[(user_id, OCCURRED_AT.date())]
    assert day["calories_kcal"] == 300.0  # replaced, not 500 + 300
    assert day["entries_logged_count"] == 1


async def test_correction_moving_to_a_different_date_updates_both_days():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    entry_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await HandleFoodEntryLoggedHandler(processed, summary).handle(
        HandleFoodEntryLoggedCommand(
            event_id=uuid.uuid4(),
            entry_id=entry_id,
            user_id=user_id,
            quantity=1.0,
            calories_kcal_per_unit=400.0,
            protein_g_per_unit=10.0,
            carbs_g_per_unit=10.0,
            fat_g_per_unit=10.0,
            occurred_at=OCCURRED_AT,
        )
    )
    new_occurred_at = OCCURRED_AT + timedelta(days=1)

    await HandleFoodEntryCorrectedHandler(processed, summary).handle(
        HandleFoodEntryCorrectedCommand(
            event_id=uuid.uuid4(),
            entry_id=entry_id,
            user_id=user_id,
            quantity=1.0,
            calories_kcal_per_unit=400.0,
            protein_g_per_unit=10.0,
            carbs_g_per_unit=10.0,
            fat_g_per_unit=10.0,
            occurred_at=new_occurred_at,
        )
    )

    old_day = summary.days[(user_id, OCCURRED_AT.date())]
    new_day = summary.days[(user_id, new_occurred_at.date())]
    assert old_day["calories_kcal"] == 0.0
    assert old_day["entries_logged_count"] == 0
    assert new_day["calories_kcal"] == 400.0
    assert new_day["entries_logged_count"] == 1


async def test_redelivered_correction_event_id_is_a_no_op():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    command = HandleFoodEntryCorrectedCommand(
        event_id=uuid.uuid4(),
        entry_id=entry_id,
        user_id=user_id,
        quantity=1.0,
        calories_kcal_per_unit=300.0,
        protein_g_per_unit=20.0,
        carbs_g_per_unit=25.0,
        fat_g_per_unit=5.0,
        occurred_at=OCCURRED_AT,
    )
    handler = HandleFoodEntryCorrectedHandler(processed, summary)

    await handler.handle(command)
    await handler.handle(command)

    assert summary.correct_food_entry_calls == 1
