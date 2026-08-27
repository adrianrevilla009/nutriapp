from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.log_water_intake import LogWaterIntakeCommand, LogWaterIntakeHandler
from application.commands.remove_water_intake import (
    RemoveWaterIntakeCommand,
    RemoveWaterIntakeHandler,
)
from application.errors import WaterIntakeAccessDeniedError, WaterIntakeEntryNotFoundError
from tests.fixtures.factories import FakeEventStore, FakeOutboxRepository

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


async def _log_intake(event_store, outbox, user_id) -> uuid.UUID:
    handler = LogWaterIntakeHandler(event_store, outbox)
    result = await handler.handle(
        LogWaterIntakeCommand(
            user_id=user_id, amount_ml=250.0, occurred_at=NOW, correlation_id="corr-1"
        )
    )
    return result.intake_id


async def test_remove_water_intake_appends_removed_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    intake_id = await _log_intake(event_store, outbox, user_id)

    handler = RemoveWaterIntakeHandler(event_store, outbox, now_fn=lambda: NOW)
    result = await handler.handle(
        RemoveWaterIntakeCommand(intake_id=intake_id, user_id=user_id, correlation_id="corr-2")
    )
    assert result.removed is True


async def test_remove_unknown_intake_raises_not_found():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = RemoveWaterIntakeHandler(event_store, outbox, now_fn=lambda: NOW)
    command = RemoveWaterIntakeCommand(
        intake_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="corr-1"
    )
    with pytest.raises(WaterIntakeEntryNotFoundError):
        await handler.handle(command)


async def test_remove_another_users_intake_raises_access_denied():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    owner_id = uuid.uuid4()
    intake_id = await _log_intake(event_store, outbox, owner_id)
    handler = RemoveWaterIntakeHandler(event_store, outbox, now_fn=lambda: NOW)
    command = RemoveWaterIntakeCommand(
        intake_id=intake_id, user_id=uuid.uuid4(), correlation_id="corr-2"
    )
    with pytest.raises(WaterIntakeAccessDeniedError):
        await handler.handle(command)
