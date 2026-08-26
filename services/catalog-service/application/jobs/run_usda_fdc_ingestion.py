"""run_usda_fdc_ingestion — same shape as run_open_food_facts_ingestion,
but rate-limit- and circuit-breaker-aware: if the USDA circuit is open
mid-run, that run's USDA phase is skipped for this cycle (logged, status
surfaced as "circuit_open" for the `ingestion_runs` audit table) rather
than raised up as a hard failure — the OFF phase proceeds independently
per implementation plan section 7's decoupled-fallback rule.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from application.commands.ingest_product_batch import (
    IngestProductBatchCommand,
    IngestProductBatchHandler,
)
from domain.ports.catalog_source_port import CatalogSourcePort

logger = structlog.get_logger()


class UsdaFdcCircuitOpenError(Exception):
    """Raised by `UsdaFdcSourceAdapter.fetch_batch` when the circuit
    breaker is open — caught here, never propagated as a hard failure."""


@dataclass(frozen=True, slots=True)
class IngestionRunSummary:
    source: str = "usda_fdc"
    items_seen: int = 0
    items_added: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    items_skipped: int = 0
    status: str = "completed"


async def run_usda_fdc_ingestion(
    *,
    source: CatalogSourcePort,
    ingest_handler: IngestProductBatchHandler,
    correlation_id: str,
    max_pages: int | None = None,
) -> IngestionRunSummary:
    seen = added = updated = unchanged = skipped = 0
    cursor: str | None = None
    pages_processed = 0

    while True:
        try:
            batch = await source.fetch_batch(cursor)
        except UsdaFdcCircuitOpenError:
            logger.warning(
                "usda_ingestion_circuit_open_skipping_cycle", correlation_id=correlation_id
            )
            return IngestionRunSummary(
                items_seen=seen,
                items_added=added,
                items_updated=updated,
                items_unchanged=unchanged,
                items_skipped=skipped,
                status="circuit_open",
            )

        if batch.records:
            result = await ingest_handler.handle(
                IngestProductBatchCommand(records=batch.records, correlation_id=correlation_id)
            )
            seen += len(batch.records)
            added += result.added
            updated += result.updated
            unchanged += result.unchanged
        skipped += batch.skipped_count

        pages_processed += 1
        logger.info(
            "usda_ingestion_page_processed",
            page=pages_processed,
            next_cursor=batch.next_cursor,
            correlation_id=correlation_id,
        )
        cursor = batch.next_cursor
        if cursor is None:
            break
        if max_pages is not None and pages_processed >= max_pages:
            break

    return IngestionRunSummary(
        items_seen=seen,
        items_added=added,
        items_updated=updated,
        items_unchanged=unchanged,
        items_skipped=skipped,
    )
