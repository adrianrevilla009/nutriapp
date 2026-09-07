from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.handle_food_entry_deleted import (
    HandleFoodEntryDeletedCommand,
    HandleFoodEntryDeletedHandler,
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


async def test_deletion_subtracts_exactly_the_entrys_contribution_not_the_whole_day():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    user_id = uuid.uuid4()
    kept_entry_id = uuid.uuid4()
    deleted_entry_id = uuid.uuid4()

    for entry_id, calories in ((kept_entry_id, 300.0), (deleted_entry_id, 500.0)):
        await HandleFoodEntryLoggedHandler(processed, summary).handle(
            HandleFoodEntryLoggedCommand(
                event_id=uuid.uuid4(),
                entry_id=entry_id,
                user_id=user_id,
                quantity=1.0,
                calories_kcal_per_unit=calories,
                protein_g_per_unit=0.0,
                carbs_g_per_unit=0.0,
                fat_g_per_unit=0.0,
                occurred_at=OCCURRED_AT,
            )
        )

    await HandleFoodEntryDeletedHandler(processed, summary).handle(
        HandleFoodEntryDeletedCommand(event_id=uuid.uuid4(), entry_id=deleted_entry_id)
    )

    day = summary.days[(user_id, OCCURRED_AT.date())]
    assert day["calories_kcal"] == 300.0  # only the deleted entry's 500 removed
    assert day["entries_logged_count"] == 1


async def test_redelivered_deletion_event_id_is_a_no_op():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    entry_id = uuid.uuid4()
    command = HandleFoodEntryDeletedCommand(event_id=uuid.uuid4(), entry_id=entry_id)
    handler = HandleFoodEntryDeletedHandler(processed, summary)

    await handler.handle(command)
    await handler.handle(command)

    assert summary.remove_food_entry_calls == 1
