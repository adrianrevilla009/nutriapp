from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from application.commands.end_fasting_window import EndFastingWindowCommand, EndFastingWindowHandler
from application.commands.start_fasting_window import (
    StartFastingWindowCommand,
    StartFastingWindowHandler,
)
from domain.entities.fasting_window import WindowNotFoundError
from tests.fixtures.factories import FakeEventStore, FakeOutboxRepository

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


async def test_end_fasting_window_appends_ended_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    start_handler = StartFastingWindowHandler(event_store, outbox, now_fn=lambda: NOW)
    user_id = uuid.uuid4()
    started = await start_handler.handle(
        StartFastingWindowCommand(user_id=user_id, correlation_id="corr-1")
    )

    end_handler = EndFastingWindowHandler(
        event_store, outbox, now_fn=lambda: NOW + timedelta(hours=16)
    )
    result = await end_handler.handle(
        EndFastingWindowCommand(
            user_id=user_id, window_id=started.window_id, correlation_id="corr-2"
        )
    )
    assert result.window_id == started.window_id
    stream = await event_store.load("fasting_window", str(user_id))
    assert [e.event_type for e in stream] == ["FastingWindowStarted", "FastingWindowEnded"]


async def test_end_fasting_window_for_another_users_window_id_raises_not_found():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    start_handler = StartFastingWindowHandler(event_store, outbox, now_fn=lambda: NOW)
    owner_id = uuid.uuid4()
    started = await start_handler.handle(
        StartFastingWindowCommand(user_id=owner_id, correlation_id="corr-1")
    )

    end_handler = EndFastingWindowHandler(event_store, outbox, now_fn=lambda: NOW)
    command = EndFastingWindowCommand(
        user_id=uuid.uuid4(), window_id=started.window_id, correlation_id="corr-2"
    )
    with pytest.raises(WindowNotFoundError):
        await end_handler.handle(command)
