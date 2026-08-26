"""OpenFoodFactsSourceAdapter — implements CatalogSourcePort.

Reads a downloaded bulk export file via `BulkExportReader`; makes no live
HTTP calls at all, so no circuit breaker is needed for the adapter itself
(implementation plan section 7). Malformed rows and rows normalization
can't identify (no barcode-or-name-worthy fields at all — missing source
identifier) are skipped-and-logged rather than crashing the whole batch.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from domain.ports.catalog_source_port import SourceBatch
from domain.services.product_normalizer import (
    EmptyRawRecordError,
    MissingSourceIdentifierError,
    normalize_open_food_facts_record,
)
from infrastructure.external.open_food_facts.bulk_export_reader import BulkExportReader

logger = structlog.get_logger()

DEFAULT_BATCH_SIZE = 500


class OpenFoodFactsSourceAdapter:
    """Implements domain.ports.catalog_source_port.CatalogSourcePort."""

    def __init__(self, export_file_path: str, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self._reader = BulkExportReader(export_file_path)
        self._batch_size = batch_size

    async def fetch_batch(self, cursor: str | None) -> SourceBatch:
        offset = int(cursor) if cursor is not None else 0
        result = self._reader.read_batch(offset=offset, batch_size=self._batch_size)

        observed_at = datetime.now(timezone.utc)
        records = []
        skipped = result.skipped_count
        for raw in result.records:
            try:
                records.append(normalize_open_food_facts_record(raw, observed_at=observed_at))
            except (EmptyRawRecordError, MissingSourceIdentifierError):
                logger.warning("off_export_row_skipped_malformed", raw_row=raw)
                skipped += 1

        return SourceBatch(
            records=tuple(records),
            next_cursor=str(result.next_offset) if result.next_offset is not None else None,
            skipped_count=skipped,
        )
