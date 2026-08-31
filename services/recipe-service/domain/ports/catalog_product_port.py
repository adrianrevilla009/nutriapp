"""CatalogProductPort -- resolves an ingredient's `catalog_product_id`
against `catalog-service`'s public `GET /api/v1/catalog/products/{id}`
endpoint. Concrete adapter:
`infrastructure.external.catalog_product_client.CatalogProductClient`.

`get_product` returns `None` for a genuine "no such product" (catalog-
service's 404 -- a well-formed, expected business response, e.g. the
product was removed since the recipe was authored) and raises
`CatalogProductUnavailableError` only for a genuine service-health
signal (circuit open, transport failure, 5xx) -- callers must never
conflate the two (`recipe-agent.md`: block publish on an unresolvable
ingredient, never on a transient outage silently misreported as
"doesn't exist")."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from domain.value_objects.nutrient_panel import NutrientPanel


class CatalogProductUnavailableError(Exception):
    """Raised when catalog-service's product endpoint cannot be reached
    (circuit open, retries exhausted, timeout) or returns an unexpected
    response -- never for a well-formed 404."""


@dataclass(frozen=True, slots=True)
class ResolvedIngredientProduct:
    product_id: uuid.UUID
    nutrition_per_100g: NutrientPanel | None


class CatalogProductPort(Protocol):
    async def get_product(self, product_id: uuid.UUID) -> ResolvedIngredientProduct | None: ...
