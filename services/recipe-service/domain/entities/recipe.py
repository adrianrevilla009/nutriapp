"""Recipe -- the write-model aggregate for this service's one aggregate
root (event-driven CRUD, ADR-0002: conventional persistence, not
event-sourced). One row per recipe.

Immutable (frozen dataclass), mirroring every other service's domain
entity convention -- every transition method returns a NEW `Recipe`
instance rather than mutating in place; the application layer is
responsible for persisting the returned instance.

`computed_totals` is ALWAYS derived from `ingredients` via
`recipe_nutrient_calculator.py` -- never accepted as a constructor
parameter from outside the `create`/`update` transition methods' own
computation, and never independently settable (recipe-agent.md's
explicit "never manually overridden" rule; enforced structurally by
`CreateRecipeHandler`/`UpdateRecipeHandler`'s command signatures, which
have no totals field at all).

Publish state: `is_published` + `unpublished_at` (nullable) together
capture the full lifecycle without a hard row delete ever occurring:
  - never published: is_published=False, unpublished_at=None
  - published: is_published=True, unpublished_at=None
  - unpublished (was published, now isn't): is_published=False,
    unpublished_at=<timestamp>
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime

from domain.value_objects.nutrient_totals import RecipeNutrientTotals
from domain.value_objects.recipe_ingredient import RecipeIngredient
from domain.value_objects.servings import Servings


@dataclass(frozen=True, slots=True)
class Recipe:
    recipe_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    instructions: str
    servings: Servings
    ingredients: tuple[RecipeIngredient, ...]
    computed_totals: RecipeNutrientTotals
    is_published: bool
    unpublished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        recipe_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        instructions: str,
        servings: Servings,
        ingredients: tuple[RecipeIngredient, ...],
        computed_totals: RecipeNutrientTotals,
        now: datetime,
    ) -> Recipe:
        return cls(
            recipe_id=recipe_id,
            user_id=user_id,
            title=title,
            instructions=instructions,
            servings=servings,
            ingredients=ingredients,
            computed_totals=computed_totals,
            is_published=False,
            unpublished_at=None,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        title: str,
        instructions: str,
        servings: Servings,
        ingredients: tuple[RecipeIngredient, ...],
        computed_totals: RecipeNutrientTotals,
        now: datetime,
    ) -> Recipe:
        """Editing ingredients/instructions/servings/title never changes
        publish state -- an already-published recipe stays published with
        its (recomputed) totals; a subsequent search re-resolves
        ingredients at THAT time regardless, per `publish()`'s own
        re-verification rule, so a stale published totals snapshot never
        silently persists past the next publish action."""
        return replace(
            self,
            title=title,
            instructions=instructions,
            servings=servings,
            ingredients=ingredients,
            computed_totals=computed_totals,
            updated_at=now,
        )

    def publish(self, now: datetime) -> Recipe:
        return replace(self, is_published=True, unpublished_at=None, updated_at=now)

    def unpublish(self, now: datetime) -> Recipe:
        """Idempotent: unpublishing an already-unpublished recipe, or a
        recipe that was never published, is a no-op that returns `self`
        unchanged -- the caller (`UnpublishRecipeHandler`/
        `DeleteRecipeHandler`) uses `self is result` to decide whether a
        `RecipeUnpublished` event is warranted."""
        if not self.is_published:
            return self
        return replace(self, is_published=False, unpublished_at=now, updated_at=now)

    @property
    def was_ever_published(self) -> bool:
        return self.is_published or self.unpublished_at is not None
