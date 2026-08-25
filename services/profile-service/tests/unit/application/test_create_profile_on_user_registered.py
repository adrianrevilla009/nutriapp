from __future__ import annotations

import uuid

import pytest

from application.commands.create_profile_on_user_registered import (
    CreateProfileOnUserRegisteredCommand,
    CreateProfileOnUserRegisteredHandler,
)
from tests.fixtures.factories import (
    FakeEventStore,
    FakeOutboxRepository,
    FakeProcessedEventsRepository,
)


@pytest.fixture
def handler():
    return CreateProfileOnUserRegisteredHandler(
        FakeEventStore(), FakeOutboxRepository(), FakeProcessedEventsRepository()
    )


async def test_valid_user_registered_creates_profile(handler):
    user_id = uuid.uuid4()
    source_event_id = uuid.uuid4()
    result = await handler.handle(
        CreateProfileOnUserRegisteredCommand(
            user_id=user_id, source_event_id=source_event_id, correlation_id="corr-1"
        )
    )
    assert result.created is True


async def test_same_event_id_delivered_twice_is_idempotent_no_op(handler):
    user_id = uuid.uuid4()
    source_event_id = uuid.uuid4()
    command = CreateProfileOnUserRegisteredCommand(
        user_id=user_id, source_event_id=source_event_id, correlation_id="corr-1"
    )
    first = await handler.handle(command)
    second = await handler.handle(command)
    assert first.created is True
    assert second.created is False


async def test_profile_created_carries_causation_id_from_source_user_registered_event():
    event_store = FakeEventStore()
    handler = CreateProfileOnUserRegisteredHandler(
        event_store, FakeOutboxRepository(), FakeProcessedEventsRepository()
    )
    user_id = uuid.uuid4()
    source_event_id = uuid.uuid4()

    await handler.handle(
        CreateProfileOnUserRegisteredCommand(
            user_id=user_id, source_event_id=source_event_id, correlation_id="corr-1"
        )
    )

    events = await event_store.load(user_id)
    assert events[0].event_type == "ProfileCreated"
    assert events[0].metadata.causation_id == str(source_event_id)
