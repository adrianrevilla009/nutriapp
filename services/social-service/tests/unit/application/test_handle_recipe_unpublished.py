from __future__ import annotations

import uuid

from application.commands.handle_recipe_unpublished import (
    HandleRecipeUnpublishedCommand,
    HandleRecipeUnpublishedHandler,
)
from tests.fixtures.factories import (
    FakeFeedRepository,
    FakeProcessedRecipeEventsRepository,
    make_feed_entry,
)


async def test_recipe_unpublished_removes_existing_feed_entry():
    entry = make_feed_entry()
    feed = FakeFeedRepository(seed=[entry])
    processed = FakeProcessedRecipeEventsRepository()
    handler = HandleRecipeUnpublishedHandler(processed, feed)

    await handler.handle(
        HandleRecipeUnpublishedCommand(event_id=uuid.uuid4(), recipe_id=entry.recipe_id)
    )

    assert entry.recipe_id not in feed.by_recipe_id
    assert feed.delete_calls == 1


async def test_recipe_unpublished_with_no_existing_entry_is_idempotent_no_op():
    feed = FakeFeedRepository()
    processed = FakeProcessedRecipeEventsRepository()
    handler = HandleRecipeUnpublishedHandler(processed, feed)

    await handler.handle(
        HandleRecipeUnpublishedCommand(event_id=uuid.uuid4(), recipe_id=uuid.uuid4())
    )

    assert feed.delete_calls == 1  # delete_by_recipe_id is a safe no-op, never raises


async def test_same_event_id_processed_twice_deletes_exactly_once():
    entry = make_feed_entry()
    feed = FakeFeedRepository(seed=[entry])
    processed = FakeProcessedRecipeEventsRepository()
    handler = HandleRecipeUnpublishedHandler(processed, feed)
    command = HandleRecipeUnpublishedCommand(event_id=uuid.uuid4(), recipe_id=entry.recipe_id)

    await handler.handle(command)
    await handler.handle(command)

    assert feed.delete_calls == 1
