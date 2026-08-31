"""Application-layer typed errors -- mapped to HTTP responses in
infrastructure/http/error_mapping.py. Domain-layer ports' own typed
errors (`UnresolvableIngredientError`'s sibling
`CatalogProductUnavailableError`, `EntitlementCheckUnavailableError`) are
mapped directly there too, without being wrapped a second time here.
"""

from __future__ import annotations


class RecipeNotFoundError(Exception):
    """Raised for a missing recipe OR a recipe owned by a different user --
    deliberately the same error/message shape for both, so a caller can
    never distinguish "doesn't exist" from "exists but isn't yours" (never
    leak existence of another user's recipe, test-plan section 1)."""


class UnresolvableIngredientError(Exception):
    """Raised when an ingredient's `catalog_product_id` does not resolve
    to a real, currently-existing `catalog-service` product -- blocks
    recipe creation/update/publish rather than persisting/publishing
    incomplete data (recipe-agent.md's explicit rule)."""


class NotEntitledError(Exception):
    """Raised when the caller is not Pro-entitled for a publish/search
    request -- rejected explicitly, never silently degraded (recipe-agent.md,
    CLAUDE.md section 2.2)."""
