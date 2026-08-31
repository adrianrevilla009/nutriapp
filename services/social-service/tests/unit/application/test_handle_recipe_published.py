from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.handle_recipe_published import (
    HandleRecipePublishedCommand,
    HandleRecipePublishedHandler,
)
from tests.fixtures.factories import FakeFeedRepository, FakeProcessedRecipeEventsRepository

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def test_recipe_published_upserts_feed_entry_and_marks_processed():
    feed = FakeFeedRepository()
    processed = FakeProcessedRecipeEventsRepository()
    handler = HandleRecipePublishedHandler(processed, feed)
    recipe_id = uuid.uuid4()
    author_id = uuid.uuid4()
    event_id = uuid.uuid4()

    await handler.handle(
        HandleRecipePublishedCommand(
            event_id=event_id,
            recipe_id=recipe_id,
            author_id=author_id,
            title="Omelette",
            published_at=NOW,
        )
    )

    entry = feed.by_recipe_id[recipe_id]
    assert entry.author_id == author_id
    assert entry.title == "Omelette"
    assert entry.published_at == NOW
    assert await processed.is_processed(event_id) is True


async def test_recipe_published_with_no_title_upserts_title_none():
    """Known gap -- RecipePublished (v1) does not carry a title today; see
    domain/value_objects/feed_entry.py's docstring."""
    feed = FakeFeedRepository()
    processed = FakeProcessedRecipeEventsRepository()
    handler = HandleRecipePublishedHandler(processed, feed)
    recipe_id = uuid.uuid4()

    await handler.handle(
        HandleRecipePublishedCommand(
            event_id=uuid.uuid4(),
            recipe_id=recipe_id,
            author_id=uuid.uuid4(),
            title=None,
            published_at=NOW,
        )
    )

    assert feed.by_recipe_id[recipe_id].title is None


async def test_same_event_id_processed_twice_writes_feed_exactly_once():
    feed = FakeFeedRepository()
    processed = FakeProcessedRecipeEventsRepository()
    handler = HandleRecipePublishedHandler(processed, feed)
    command = HandleRecipePublishedCommand(
        event_id=uuid.uuid4(),
        recipe_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        title="Omelette",
        published_at=NOW,
    )

    await handler.handle(command)
    await handler.handle(command)

    assert feed.upsert_calls == 1
