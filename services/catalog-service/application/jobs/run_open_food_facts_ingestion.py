"""run_open_food_facts_ingestion — orchestrates a bounded ingestion run
over one Open Food Facts bulk export file/delta, paging through
`CatalogSourcePort.fetch_batch` and calling `IngestProductBatchHandler`
per page.

Scheduling trigger is external (implementation plan section 7/9.2) — this
job is manually triggerable but not wired to any scheduler. Executing a
real, production-scale run requires the standing CLAUDE.md section 7
human-confirmation gate at execution time (implementation plan section
9.1) — this module only defines the *mechanism*.
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


@dataclass(frozen=True, slots=True)
class IngestionRunSummary:
    source: str
    items_seen: int = 0
    items_added: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    items_skipped: int = 0
    status: str = "completed"


async def run_open_food_facts_ingestion(
    *,
    source: CatalogSourcePort,
    ingest_handler: IngestProductBatchHandler,
    correlation_id: str,
    max_pages: int | None = None,
) -> IngestionRunSummary:
    summary = IngestionRunSummary(source="open_food_facts")
    cursor: str | None = None
    pages_processed = 0

    while True:
        batch = await source.fetch_batch(cursor)
        if batch.records:
            result = await ingest_handler.handle(
                IngestProductBatchCommand(records=batch.records, correlation_id=correlation_id)
            )
            summary = IngestionRunSummary(
                source="open_food_facts",
                items_seen=summary.items_seen + len(batch.records),
                items_added=summary.items_added + result.added,
                items_updated=summary.items_updated + result.updated,
                items_unchanged=summary.items_unchanged + result.unchanged,
                items_skipped=summary.items_skipped + batch.skipped_count,
            )
        else:
            summary = IngestionRunSummary(
                source="open_food_facts",
                items_seen=summary.items_seen,
                items_added=summary.items_added,
                items_updated=summary.items_updated,
                items_unchanged=summary.items_unchanged,
                items_skipped=summary.items_skipped + batch.skipped_count,
            )

        pages_processed += 1
        logger.info(
            "off_ingestion_page_processed",
            page=pages_processed,
            next_cursor=batch.next_cursor,
            correlation_id=correlation_id,
        )
        cursor = batch.next_cursor
        if cursor is None:
            break
        if max_pages is not None and pages_processed >= max_pages:
            break

    return summary
