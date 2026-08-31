"""FeedEntry -- one projected row of this service's local `feed_entries`
read table, sourced from consuming `recipe-service`'s `RecipePublished`/
`RecipeUnpublished` events (fan-out-on-read, implementation plan section
1.3). Never a copy of the full recipe -- only the fields a feed listing
needs (CLAUDE.md section 2.5's "own local copy, never the write model"
convention).

**Known, flagged gap** (see `application/commands/handle_recipe_published.py`
and the final implementation report): `recipe-service`'s `RecipePublished`
(v1) payload, as actually published today
(`packages/shared-contracts/schemas/recipe_published.v1.json`), is
`{recipe_id, user_id, published_at}` -- it carries NO `title` field, even
though this plan's file list names `title` as one of `feed_entries`'
columns. Rather than block on a cross-service event-schema change (out of
scope for this plan -- section 6 explicitly makes no `recipe-service` code
changes) or add a forbidden synchronous call back to `recipe-service`
(section 1.8), `title` is modeled here as OPTIONAL (`str | None`) and is
`None` for every entry projected from today's `RecipePublished` schema.
The field is kept (not dropped) so a future `RecipePublished` v2 that adds
`title` requires no `feed_entries`/`FeedEntry` schema change -- only the
event-payload parsing in `handle_recipe_published.py` needs to start
populating it. Flagged explicitly for `architecture-agent`/`reviewer-agent`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


class InvalidFeedEntryError(ValueError):
    """Raised for a structurally invalid feed entry -- a non-empty title,
    when present at all, must not be blank/whitespace-only."""


@dataclass(frozen=True, slots=True)
class FeedEntry:
    recipe_id: uuid.UUID
    author_id: uuid.UUID
    title: str | None
    published_at: datetime

    def __post_init__(self) -> None:
        if self.title is not None and not self.title.strip():
            raise InvalidFeedEntryError("FeedEntry title, if provided, must not be blank.")
