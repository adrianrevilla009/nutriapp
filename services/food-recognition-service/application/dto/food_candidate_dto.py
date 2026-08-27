"""Read-facing DTOs are not needed beyond the domain value objects
themselves for this service (they are already simple, immutable, and
serialization-friendly) -- HTTP schemas map directly from
`domain.value_objects.food_candidate.FoodCandidate` and
`domain.value_objects.catalog_product.CatalogProduct`. This module is kept
as the designated seam (implementation plan section 3's
`application/dto/`) in case a future use case needs a shape that diverges
from the domain object -- none does yet.
"""

from __future__ import annotations
