"""UsdaFdcSourceAdapter — implements CatalogSourcePort.

Live HTTP via `UsdaFdcClient`, wrapped in `UsdaFdcCircuitBreaker`
(purgatory) + `UsdaFdcClient`'s own `tenacity` retry. A 429/proactive
rate-limit hit or an open circuit both degrade gracefully: this method
never raises up as a hard ingestion failure (test-plan section 2) — it
ends the current run's paging cleanly (`next_cursor=None`) rather than
retrying in a tight loop within the same run (catalog-agent.md: "never a
tight-loop bulk ingestion").
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from application.jobs.run_usda_fdc_ingestion import UsdaFdcCircuitOpenError
from domain.ports.catalog_source_port import SourceBatch
from domain.services.product_normalizer import (
    EmptyRawRecordError,
    MissingSourceIdentifierError,
    normalize_usda_fdc_record,
)
from infrastructure.external.usda_fdc.circuit_breaker import UsdaFdcCircuitBreaker
from infrastructure.external.usda_fdc.usda_fdc_client import UsdaFdcClient, UsdaFdcRateLimitedError

logger = structlog.get_logger()

DEFAULT_PAGE_SIZE = 200


class UsdaFdcSourceAdapter:
    """Implements domain.ports.catalog_source_port.CatalogSourcePort."""

    def __init__(
        self,
        client: UsdaFdcClient,
        circuit_breaker: UsdaFdcCircuitBreaker,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        self._client = client
        self._breaker = circuit_breaker
        self._page_size = page_size

    async def fetch_batch(self, cursor: str | None) -> SourceBatch:
        page_number = int(cursor) if cursor is not None else 1

        try:
            data = await self._breaker.call(
                self._client.fetch_branded_foods_page, page_number, self._page_size
            )
        except UsdaFdcRateLimitedError:
            logger.warning("usda_fdc_rate_limited_backing_off", page=page_number)
            return SourceBatch(records=(), next_cursor=None, skipped_count=1)
        except UsdaFdcCircuitOpenError:
            # Propagated to the ingestion job, which treats it as this
            # cycle's USDA phase being skipped entirely (implementation
            # plan section 7's decoupled-fallback rule) — re-raised here
            # rather than swallowed, since the job needs to distinguish
            # "circuit open, skip this whole cycle" from "one page
            # rate-limited, stop paging but keep what we got."
            raise

        observed_at = datetime.now(timezone.utc)
        foods = data.get("foods", [])
        records = []
        skipped = 0
        for raw in foods:
            try:
                records.append(normalize_usda_fdc_record(raw, observed_at=observed_at))
            except (EmptyRawRecordError, MissingSourceIdentifierError):
                logger.warning("usda_fdc_row_skipped_malformed", raw_row=raw)
                skipped += 1

        total_pages = data.get("totalPages", page_number)
        next_cursor = str(page_number + 1) if page_number < total_pages else None

        return SourceBatch(records=tuple(records), next_cursor=next_cursor, skipped_count=skipped)
