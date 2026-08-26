"""Application-layer error types — orchestration failures that aren't
domain invariant violations."""

from __future__ import annotations


class UnsupportedSearchFilterError(ValueError):
    """Raised for a dietary/allergen filter value the API doesn't recognize
    — mapped to HTTP 422, never a 500 (test-plan section 3)."""


class ProductNotFoundError(LookupError):
    """Raised when a product id doesn't exist — mapped to HTTP 404."""
