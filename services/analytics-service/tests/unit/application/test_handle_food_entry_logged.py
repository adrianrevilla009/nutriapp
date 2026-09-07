from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.handle_food_entry_logged import (
    HandleFoodEntryLoggedCommand,
    HandleFoodEntryLoggedHandler,
)
from tests.fixtures.factories import (
    FakeDailyLogSummaryRepository,
    FakeProcessedDiaryEventsRepository,
)

OCCURRED_AT = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)


def _command(**overrides) -> HandleFoodEntryLoggedCommand:
    defaults = dict(
        event_id=uuid.uuid4(),
        entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        quantity=2.0,
        calories_kcal_per_unit=100.0,
        protein_g_per_unit=10.0,
        carbs_g_per_unit=20.0,
        fat_g_per_unit=5.0,
        occurred_at=OCCURRED_AT,
    )
    defaults.update(overrides)
    return HandleFoodEntryLoggedCommand(**defaults)


async def test_valid_event_upserts_daily_log_summary_scaled_by_quantity():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    handler = HandleFoodEntryLoggedHandler(processed, summary)
    command = _command()

    await handler.handle(command)

    day = summary.days[(command.user_id, OCCURRED_AT.date())]
    assert day["calories_kcal"] == 200.0
    assert day["protein_g"] == 20.0
    assert day["entries_logged_count"] == 1
    assert summary.apply_food_entry_calls == 1


async def test_redelivered_event_id_is_a_no_op():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    handler = HandleFoodEntryLoggedHandler(processed, summary)
    command = _command()

    await handler.handle(command)
    await handler.handle(command)

    day = summary.days[(command.user_id, OCCURRED_AT.date())]
    assert day["calories_kcal"] == 200.0
    assert day["entries_logged_count"] == 1
