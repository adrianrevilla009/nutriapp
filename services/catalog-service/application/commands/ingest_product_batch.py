"""IngestProductBatchCommand + handler.

Orchestrates: dedup-key resolution -> load existing (if any) -> merge ->
upsert -> outbox, for a batch of already-normalized `RawProductRecord`s
(one or more source adapters' output). This is the one place ingestion
writes reach the `products` table — both `run_open_food_facts_ingestion`
and `run_usda_fdc_ingestion` jobs page through their source and call this
same handler per batch, per implementation plan section 3.
"""

from __future__ import annotations

from dataclasses import dataclass

from application.dto.raw_product_record import RawProductRecord
from domain.entities.product import Product
from domain.events.product_catalogued import build_product_catalogued_event
from domain.events.product_updated import build_product_updated_event
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.product_repository_port import ProductRepositoryPort


@dataclass(frozen=True, slots=True)
class IngestProductBatchCommand:
    records: tuple[RawProductRecord, ...]
    correlation_id: str


@dataclass(frozen=True, slots=True)
class IngestProductBatchResult:
    added: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def total(self) -> int:
        return self.added + self.updated + self.unchanged


class IngestProductBatchHandler:
    def __init__(
        self,
        product_repository: ProductRepositoryPort,
        outbox_repository: OutboxRepositoryPort,
    ) -> None:
        self._products = product_repository
        self._outbox = outbox_repository

    async def _find_existing(self, record: RawProductRecord) -> Product | None:
        if record.barcode is not None:
            return await self._products.get_by_barcode(record.barcode)
        return await self._products.get_by_source_reference(
            record.source.value, record.source_product_id
        )

    async def handle(self, command: IngestProductBatchCommand) -> IngestProductBatchResult:
        added = updated = unchanged = 0
        for record in command.records:
            existing = await self._find_existing(record)
            result = Product.merge(existing=existing, incoming=record)

            if result.is_new:
                await self._products.save(result.product)
                event = build_product_catalogued_event(
                    product=result.product, correlation_id=command.correlation_id
                )
                await self._outbox.enqueue(event)
                added += 1
            elif result.changed_fields:
                await self._products.save(result.product)
                event = build_product_updated_event(
                    product=result.product,
                    changed_fields=result.changed_fields,
                    correlation_id=command.correlation_id,
                )
                await self._outbox.enqueue(event)
                updated += 1
            elif result.product is not existing:
                # A newly-seen source corroborated existing data (no
                # field-level conflict) — still persisted so the new
                # source's raw snapshot isn't lost, no event published.
                await self._products.save(result.product)
                unchanged += 1
            else:
                unchanged += 1

        return IngestProductBatchResult(added=added, updated=updated, unchanged=unchanged)
