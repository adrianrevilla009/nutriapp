from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.handle_weight_recorded import (
    HandleWeightRecordedCommand,
    HandleWeightRecordedHandler,
)
from tests.fixtures.factories import FakeProcessedProfileEventsRepository, FakeWeightTrendRepository

RECORDED_AT = datetime(2026, 6, 8, tzinfo=timezone.utc)


async def test_valid_event_stores_ciphertext_untouched():
    processed = FakeProcessedProfileEventsRepository()
    weight_trend = FakeWeightTrendRepository()
    user_id = uuid.uuid4()
    ciphertext = "base64-aes-gcm-ciphertext=="
    handler = HandleWeightRecordedHandler(processed, weight_trend)

    await handler.handle(
        HandleWeightRecordedCommand(
            event_id=uuid.uuid4(),
            user_id=user_id,
            weight_kg_ciphertext=ciphertext,
            recorded_at=RECORDED_AT,
        )
    )

    row = weight_trend.rows[(user_id, RECORDED_AT.date())]
    assert row["weight_kg_ciphertext"] == ciphertext  # stored verbatim, never decrypted


async def test_redelivered_event_id_is_a_no_op():
    processed = FakeProcessedProfileEventsRepository()
    weight_trend = FakeWeightTrendRepository()
    command = HandleWeightRecordedCommand(
        event_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        weight_kg_ciphertext="x",
        recorded_at=RECORDED_AT,
    )
    handler = HandleWeightRecordedHandler(processed, weight_trend)

    await handler.handle(command)
    await handler.handle(command)

    assert weight_trend.upsert_calls == 1
