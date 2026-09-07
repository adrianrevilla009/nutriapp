from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.handle_water_intake_logged import (
    HandleWaterIntakeLoggedCommand,
    HandleWaterIntakeLoggedHandler,
)
from application.commands.handle_water_intake_removed import (
    HandleWaterIntakeRemovedCommand,
    HandleWaterIntakeRemovedHandler,
)
from tests.fixtures.factories import (
    FakeDailyLogSummaryRepository,
    FakeProcessedDiaryEventsRepository,
)

OCCURRED_AT = datetime(2026, 6, 8, 8, 0, tzinfo=timezone.utc)


async def test_removal_does_not_double_subtract_on_redelivery():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    user_id = uuid.uuid4()
    intake_id = uuid.uuid4()

    await HandleWaterIntakeLoggedHandler(processed, summary).handle(
        HandleWaterIntakeLoggedCommand(
            event_id=uuid.uuid4(),
            intake_id=intake_id,
            user_id=user_id,
            amount_ml=300.0,
            occurred_at=OCCURRED_AT,
        )
    )

    remove_command = HandleWaterIntakeRemovedCommand(event_id=uuid.uuid4(), intake_id=intake_id)
    handler = HandleWaterIntakeRemovedHandler(processed, summary)
    await handler.handle(remove_command)
    await handler.handle(remove_command)  # redelivery of the SAME removal event_id

    day = summary.days[(user_id, OCCURRED_AT.date())]
    assert day["water_ml"] == 0.0  # not -300
    assert summary.remove_water_intake_calls == 1
