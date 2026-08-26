from application.commands.ingest_product_batch import (
    IngestProductBatchCommand,
    IngestProductBatchHandler,
)
from domain.value_objects.source_reference import SourceName
from tests.fixtures.factories import (
    FakeOutboxRepository,
    FakeProductRepository,
    make_raw_record,
)


async def test_ingest_new_product_publishes_product_catalogued():
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    handler = IngestProductBatchHandler(products, outbox)

    result = await handler.handle(
        IngestProductBatchCommand(records=(make_raw_record(),), correlation_id="c1")
    )

    assert result.added == 1
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "ProductCatalogued"


async def test_ingest_changed_field_publishes_product_updated():
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    handler = IngestProductBatchHandler(products, outbox)

    await handler.handle(
        IngestProductBatchCommand(records=(make_raw_record(),), correlation_id="c1")
    )
    result = await handler.handle(
        IngestProductBatchCommand(
            records=(make_raw_record(name="Chocolate Bar Deluxe"),), correlation_id="c2"
        )
    )

    assert result.updated == 1
    assert outbox.enqueued[-1].event_type == "ProductUpdated"
    assert "name" in outbox.enqueued[-1].payload["changed_fields"]


async def test_ingest_no_op_publishes_no_event():
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    handler = IngestProductBatchHandler(products, outbox)

    await handler.handle(
        IngestProductBatchCommand(records=(make_raw_record(),), correlation_id="c1")
    )
    result = await handler.handle(
        IngestProductBatchCommand(records=(make_raw_record(),), correlation_id="c2")
    )

    assert result.unchanged == 1
    assert len(outbox.enqueued) == 1


async def test_ingest_new_corroborating_source_persists_without_event():
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    handler = IngestProductBatchHandler(products, outbox)

    await handler.handle(
        IngestProductBatchCommand(records=(make_raw_record(),), correlation_id="c1")
    )
    result = await handler.handle(
        IngestProductBatchCommand(
            records=(make_raw_record(source=SourceName.USDA_FDC, source_product_id="usda-1"),),
            correlation_id="c2",
        )
    )

    assert result.unchanged == 1
    assert len(outbox.enqueued) == 1  # still just the original ProductCatalogued
    saved_product = next(iter(products.by_id.values()))
    assert SourceName.USDA_FDC in saved_product.sources
