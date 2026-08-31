from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from domain.value_objects.feed_entry import FeedEntry, InvalidFeedEntryError

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_valid_feed_entry_with_title():
    entry = FeedEntry(
        recipe_id=uuid.uuid4(), author_id=uuid.uuid4(), title="Omelette", published_at=NOW
    )
    assert entry.title == "Omelette"


def test_valid_feed_entry_with_no_title():
    """Known gap: RecipePublished (v1) does not carry a title today -- see
    domain/value_objects/feed_entry.py's docstring. title=None is a valid,
    expected state, not an error."""
    entry = FeedEntry(recipe_id=uuid.uuid4(), author_id=uuid.uuid4(), title=None, published_at=NOW)
    assert entry.title is None


def test_blank_title_rejected():
    with pytest.raises(InvalidFeedEntryError):
        FeedEntry(recipe_id=uuid.uuid4(), author_id=uuid.uuid4(), title="   ", published_at=NOW)
