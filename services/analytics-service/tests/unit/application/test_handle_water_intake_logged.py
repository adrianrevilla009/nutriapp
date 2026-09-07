from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.handle_water_intake_logged import (
    HandleWaterIntakeLoggedCommand,
    HandleWaterIntakeLoggedHandler,
)
from tests.fixtures.factories import (
    FakeDailyLogSummaryRepository,
    FakeProcessedDiaryEventsRepository,
)

OCCURRED_AT = datetime(2026, 6, 8, 8, 0, tzinfo=timezone.utc)


async def test_valid_event_upserts_water_ml():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    user_id = uuid.uuid4()
    handler = HandleWaterIntakeLoggedHandler(processed, summary)

    await handler.handle(
        HandleWaterIntakeLoggedCommand(
            event_id=uuid.uuid4(),
            intake_id=uuid.uuid4(),
            user_id=user_id,
            amount_ml=250.0,
            occurred_at=OCCURRED_AT,
        )
    )

    assert summary.days[(user_id, OCCURRED_AT.date())]["water_ml"] == 250.0


async def test_redelivered_event_id_is_a_no_op():
    processed = FakeProcessedDiaryEventsRepository()
    summary = FakeDailyLogSummaryRepository()
    command = HandleWaterIntakeLoggedCommand(
        event_id=uuid.uuid4(),
        intake_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        amount_ml=250.0,
        occurred_at=OCCURRED_AT,
    )
    handler = HandleWaterIntakeLoggedHandler(processed, summary)

    await handler.handle(command)
    await handler.handle(command)

    assert summary.apply_water_intake_calls == 1
