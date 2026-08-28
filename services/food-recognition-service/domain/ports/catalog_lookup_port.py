"""CatalogLookupPort -- resolves a decoded barcode to a catalog product via
`catalog-service`'s internal lookup endpoint. Concrete adapter:
`infrastructure.external.catalog_lookup_client.CatalogLookupClient`.
"""

from __future__ import annotations

from typing import Protocol

from domain.value_objects.barcode import Barcode
from domain.value_objects.catalog_product import CatalogProduct


class CatalogLookupUnavailableError(Exception):
    """Raised when catalog-service's internal lookup endpoint cannot be
    reached (circuit open, retries exhausted, timeout) or returns an
    unexpected response. The caller (`DecodeBarcodeHandler`) must defer to
    `status="unavailable"` -- never guess a product match."""


class CatalogLookupPort(Protocol):
    async def lookup_by_barcode(self, barcode: Barcode) -> CatalogProduct | None: ...
