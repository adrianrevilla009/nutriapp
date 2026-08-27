"""NutrientPanelMirrorPort -- this service's local, read-only,
denormalized mirror of catalog-service's nutrient panel (implementation
plan section 6(c)), built by consuming `ProductCatalogued`/`ProductUpdated`
and keyed by `source_reference_id` (catalog-service's `product_id`, as a
string, matching diary-service's `FoodEntryLogged.source.source_reference_id`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class NutrientPanelMirrorPort(Protocol):
    async def get_by_reference_id(
        self, source_reference_id: str
    ) -> Mapping[str, float | None] | None: ...

    async def upsert(self, source_reference_id: str, panel: Mapping[str, float | None]) -> None: ...
