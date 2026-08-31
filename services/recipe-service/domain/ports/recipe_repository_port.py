"""RecipeRepositoryPort -- the write-model persistence boundary for the
`Recipe` aggregate (event-driven CRUD, ADR-0002), plus the two read
queries `list_own_recipes`/`search_published_recipes` need. Kept on one
port (not split into a separate read port) since this service has no
CQRS split -- conventional persistence, per implementation plan section
2.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.recipe import Recipe


class RecipeRepositoryPort(Protocol):
    async def get_by_id(self, recipe_id: uuid.UUID) -> Recipe | None: ...

    async def list_by_user_id(self, user_id: uuid.UUID) -> list[Recipe]: ...

    async def search_published(self, query: str) -> list[Recipe]: ...

    async def save(self, recipe: Recipe) -> None: ...
