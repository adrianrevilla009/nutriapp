from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.log_water_intake import LogWaterIntakeCommand, LogWaterIntakeHandler
from tests.fixtures.factories import FakeEventStore, FakeOutboxRepository

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


async def test_log_water_intake_appends_event_and_enqueues_outbox():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = LogWaterIntakeHandler(event_store, outbox)

    user_id = uuid.uuid4()
    result = await handler.handle(
        LogWaterIntakeCommand(
            user_id=user_id, amount_ml=250.0, occurred_at=NOW, correlation_id="corr-1"
        )
    )

    stream = await event_store.load("water_intake_entry", str(result.intake_id))
    assert len(stream) == 1
    assert stream[0].event_type == "WaterIntakeLogged"
    assert len(outbox.enqueued) == 1
