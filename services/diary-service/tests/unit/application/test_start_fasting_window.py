from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.start_fasting_window import (
    StartFastingWindowCommand,
    StartFastingWindowHandler,
)
from domain.entities.fasting_window import OverlappingFastingWindowError
from tests.fixtures.factories import FakeEventStore, FakeOutboxRepository

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


async def test_start_fasting_window_appends_started_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = StartFastingWindowHandler(event_store, outbox, now_fn=lambda: NOW)

    user_id = uuid.uuid4()
    result = await handler.handle(
        StartFastingWindowCommand(user_id=user_id, correlation_id="corr-1")
    )

    stream = await event_store.load("fasting_window", str(user_id))
    assert len(stream) == 1
    assert stream[0].event_type == "FastingWindowStarted"
    assert result.window_id is not None


async def test_start_fasting_window_while_open_raises_overlap_error():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = StartFastingWindowHandler(event_store, outbox, now_fn=lambda: NOW)
    user_id = uuid.uuid4()
    await handler.handle(StartFastingWindowCommand(user_id=user_id, correlation_id="corr-1"))

    with pytest.raises(OverlappingFastingWindowError):
        await handler.handle(StartFastingWindowCommand(user_id=user_id, correlation_id="corr-2"))
