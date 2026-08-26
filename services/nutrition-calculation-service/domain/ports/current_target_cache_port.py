"""CurrentTargetCachePort -- cache-aside for the current nutrition target
read path (caching-strategy SKILL.md). Key namespace `nutrition:current-target:*`,
1h TTL (implementation plan section 7). Invalidated event-driven on
`NutritionTargetUpdated`, TTL as a safety net.

Caches the domain entity itself (never an application-layer DTO -- ADR-0001
dependencies point inward only; the infrastructure adapter is free to
serialize `NutritionTarget` however it likes, but this port's signature
must not import outward from `application/`)."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.nutrition_target import NutritionTarget

CURRENT_TARGET_CACHE_TTL_SECONDS = 3600


class CurrentTargetCachePort(Protocol):
    async def get(self, user_id: uuid.UUID) -> NutritionTarget | None: ...

    async def set(self, user_id: uuid.UUID, target: NutritionTarget) -> None: ...

    async def invalidate(self, user_id: uuid.UUID) -> None: ...
