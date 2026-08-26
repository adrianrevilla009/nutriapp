"""UpsertNutrientPanelMirrorEntryCommand -- triggered by
`RabbitMqCatalogProductConsumer` on `ProductCatalogued`/`ProductUpdated`
(implementation plan section 6(c)): maintains this service's local,
read-only mirror of catalog-service's nutrient panel, keyed by
`source_reference_id` (catalog-service's `product_id`). Upsert, never
append -- the mirror always reflects catalog-service's latest-known
values, matching test-plan section 2's "upsert on ProductCatalogued, then
ProductUpdated for the same key updates in place" expectation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from domain.ports.nutrient_panel_mirror_port import NutrientPanelMirrorPort
from domain.services.nutrient_vocabulary_translator import translate_catalog_nutrition


@dataclass(frozen=True, slots=True)
class UpsertNutrientPanelMirrorEntryCommand:
    source_reference_id: str
    nutrition_per_100g: Mapping[str, float | None] | None


class UpsertNutrientPanelMirrorEntryHandler:
    def __init__(self, mirror_port: NutrientPanelMirrorPort) -> None:
        self._mirror_port = mirror_port

    async def handle(self, command: UpsertNutrientPanelMirrorEntryCommand) -> None:
        if command.nutrition_per_100g is None:
            # Product exists in the catalog but has no nutrition data yet --
            # nothing to mirror; a later ProductUpdated will complete it.
            return
        canonical_panel = translate_catalog_nutrition(command.nutrition_per_100g)
        await self._mirror_port.upsert(command.source_reference_id, canonical_panel)
