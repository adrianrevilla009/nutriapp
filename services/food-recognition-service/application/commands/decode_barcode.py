"""DecodeBarcodeCommand/Handler -- implements implementation plan section
1's acceptance criterion 3. Barcode lookups are free/local (no LLM call)
and are therefore never gated by the photo-analysis feature flag
(implementation plan section 8.3's acceptance criterion 9: "barcode
lookup, being free/local, is not gated").

No domain event is published for a barcode lookup (implementation plan
section 1, acceptance criterion 4's rationale) -- only the audit-record
repository write.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import InvalidImageError
from domain.entities.barcode_lookup import BarcodeLookup
from domain.ports.barcode_decoder_port import BarcodeDecoderPort
from domain.ports.barcode_lookup_repository_port import BarcodeLookupRepositoryPort
from domain.ports.catalog_lookup_port import CatalogLookupPort, CatalogLookupUnavailableError
from domain.value_objects.barcode_lookup_status import BarcodeLookupStatus
from domain.value_objects.catalog_product import CatalogProduct


@dataclass(frozen=True, slots=True)
class DecodeBarcodeCommand:
    user_id: uuid.UUID
    image_bytes: bytes
    correlation_id: str


@dataclass(frozen=True, slots=True)
class DecodeBarcodeResult:
    lookup_id: uuid.UUID
    status: BarcodeLookupStatus
    product: CatalogProduct | None


class DecodeBarcodeHandler:
    def __init__(
        self,
        barcode_decoder: BarcodeDecoderPort,
        catalog_lookup: CatalogLookupPort,
        repository: BarcodeLookupRepositoryPort,
    ) -> None:
        self._barcode_decoder = barcode_decoder
        self._catalog_lookup = catalog_lookup
        self._repository = repository

    async def handle(self, command: DecodeBarcodeCommand) -> DecodeBarcodeResult:
        if not command.image_bytes:
            raise InvalidImageError("Uploaded photo is empty.")

        now = datetime.now(timezone.utc)
        lookup_id = uuid.uuid4()

        barcode = self._barcode_decoder.decode(command.image_bytes)
        if barcode is None:
            await self._repository.save(
                BarcodeLookup(
                    lookup_id=lookup_id,
                    user_id=command.user_id,
                    submitted_at=now,
                    decoded_barcode=None,
                    matched_product_id=None,
                    status="no_match",
                )
            )
            return DecodeBarcodeResult(lookup_id=lookup_id, status="no_match", product=None)

        try:
            product = await self._catalog_lookup.lookup_by_barcode(barcode)
        except CatalogLookupUnavailableError:
            await self._repository.save(
                BarcodeLookup(
                    lookup_id=lookup_id,
                    user_id=command.user_id,
                    submitted_at=now,
                    decoded_barcode=str(barcode),
                    matched_product_id=None,
                    status="unavailable",
                )
            )
            return DecodeBarcodeResult(lookup_id=lookup_id, status="unavailable", product=None)

        status: BarcodeLookupStatus = "matched" if product is not None else "no_match"
        await self._repository.save(
            BarcodeLookup(
                lookup_id=lookup_id,
                user_id=command.user_id,
                submitted_at=now,
                decoded_barcode=str(barcode),
                matched_product_id=product.product_id if product is not None else None,
                status=status,
            )
        )
        return DecodeBarcodeResult(lookup_id=lookup_id, status=status, product=product)
