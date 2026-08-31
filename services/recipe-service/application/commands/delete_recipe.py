"""DeleteRecipeHandler -- backs `DELETE /api/v1/recipes/{recipe_id}`.

recipe-agent.md's rule applies equally to "delete" as to "unpublish":
removes the recipe from cross-user search WITHOUT deleting the author's
own record/event history -- this is always a soft-unpublish (identical
transition to `UnpublishRecipeHandler`), never a hard row delete, even
though the HTTP verb is DELETE. Kept as its own handler (rather than a
thin route-level alias for `UnpublishRecipeHandler`) to keep the two HTTP
operations independently testable/documented per implementation plan
section 3's file list, even though the underlying domain transition is
identical.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import RecipeNotFoundError
from domain.entities.recipe import Recipe
from domain.events.recipe_unpublished import build_recipe_unpublished_event
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.recipe_repository_port import RecipeRepositoryPort


@dataclass(frozen=True, slots=True)
class DeleteRecipeCommand:
    recipe_id: uuid.UUID
    user_id: uuid.UUID
    correlation_id: str


class DeleteRecipeHandler:
    def __init__(
        self,
        recipes: RecipeRepositoryPort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._recipes = recipes
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: DeleteRecipeCommand) -> Recipe:
        recipe = await self._recipes.get_by_id(command.recipe_id)
        if recipe is None or recipe.user_id != command.user_id:
            raise RecipeNotFoundError(f"Recipe {command.recipe_id} not found.")

        was_published = recipe.is_published
        unpublished = recipe.unpublish(self._now_fn())
        await self._recipes.save(unpublished)

        if was_published:
            await self._outbox.enqueue(
                build_recipe_unpublished_event(
                    recipe_id=unpublished.recipe_id,
                    user_id=unpublished.user_id,
                    correlation_id=command.correlation_id,
                )
            )
        return unpublished
