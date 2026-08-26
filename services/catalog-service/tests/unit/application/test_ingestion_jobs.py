from application.commands.ingest_product_batch import IngestProductBatchHandler
from application.jobs.run_open_food_facts_ingestion import run_open_food_facts_ingestion
from application.jobs.run_usda_fdc_ingestion import (
    UsdaFdcCircuitOpenError,
    run_usda_fdc_ingestion,
)
from domain.ports.catalog_source_port import SourceBatch
from domain.value_objects.barcode import Barcode
from domain.value_objects.source_reference import SourceName
from tests.fixtures.factories import (
    FakeOutboxRepository,
    FakeProductRepository,
    make_raw_record,
)


class _PagedFakeSource:
    def __init__(self, batches):
        self._batches = {b_cursor: b for b_cursor, b in batches}

    async def fetch_batch(self, cursor):
        return self._batches[cursor]


async def test_off_ingestion_job_pages_through_cursor_until_none():
    batch_1 = SourceBatch(
        records=(make_raw_record(source_product_id="off-1", barcode=Barcode("5901234123457")),),
        next_cursor="p2",
    )
    batch_2 = SourceBatch(
        records=(make_raw_record(source_product_id="off-2", barcode=Barcode("036000291452")),),
        next_cursor=None,
    )
    source = _PagedFakeSource([(None, batch_1), ("p2", batch_2)])
    handler = IngestProductBatchHandler(FakeProductRepository(), FakeOutboxRepository())

    summary = await run_open_food_facts_ingestion(
        source=source, ingest_handler=handler, correlation_id="c1"
    )

    assert summary.items_seen == 2
    assert summary.items_added == 2
    assert summary.status == "completed"


async def test_usda_ingestion_job_degrades_gracefully_on_open_circuit():
    class _OpenCircuitSource:
        async def fetch_batch(self, cursor):
            raise UsdaFdcCircuitOpenError("circuit open")

    handler = IngestProductBatchHandler(FakeProductRepository(), FakeOutboxRepository())

    summary = await run_usda_fdc_ingestion(
        source=_OpenCircuitSource(), ingest_handler=handler, correlation_id="c1"
    )

    assert summary.status == "circuit_open"
    assert summary.items_seen == 0


async def test_usda_ingestion_job_pages_through_cursor_until_none():
    batch_1 = SourceBatch(
        records=(make_raw_record(source=SourceName.USDA_FDC, source_product_id="usda-1"),),
        next_cursor="p2",
    )
    batch_2 = SourceBatch(records=(), next_cursor=None, skipped_count=1)
    source = _PagedFakeSource([(None, batch_1), ("p2", batch_2)])
    handler = IngestProductBatchHandler(FakeProductRepository(), FakeOutboxRepository())

    summary = await run_usda_fdc_ingestion(
        source=source, ingest_handler=handler, correlation_id="c1"
    )

    assert summary.items_added == 1
    assert summary.items_skipped == 1
    assert summary.status == "completed"
