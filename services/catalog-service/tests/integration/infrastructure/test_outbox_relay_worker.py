import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.product import Product
from domain.events.product_catalogued import build_product_catalogued_event
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_product_repository import PostgresProductRepository
from tests.fixtures.factories import make_raw_record

pytestmark = pytest.mark.usefixtures("db_engine")


class _FakePublisher:
    def __init__(self, fail: bool = False) -> None:
        self.published = []
        self.fail = fail

    async def publish(self, event) -> None:
        if self.fail:
            raise RuntimeError("publish failed")
        self.published.append(event)


async def test_outbox_row_inserted_in_same_transaction_is_relayed(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        repo = PostgresProductRepository(session)
        product = Product.merge(existing=None, incoming=make_raw_record()).product
        await repo.save(product)
        outbox = PostgresOutboxRepository(session)
        event = build_product_catalogued_event(product=product, correlation_id="c1")
        await outbox.enqueue(event)
        await session.commit()

    publisher = _FakePublisher()
    worker = OutboxRelayWorker(session_factory, publisher)
    published_count = await worker.relay_once()

    assert published_count == 1
    assert publisher.published[0].event_type == "ProductCatalogued"


async def test_publish_failure_leaves_row_unpublished_for_retry(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        repo = PostgresProductRepository(session)
        product = Product.merge(
            existing=None, incoming=make_raw_record(source_product_id="off-retry")
        ).product
        await repo.save(product)
        outbox = PostgresOutboxRepository(session)
        event = build_product_catalogued_event(product=product, correlation_id="c1")
        await outbox.enqueue(event)
        await session.commit()

    failing_publisher = _FakePublisher(fail=True)
    worker = OutboxRelayWorker(session_factory, failing_publisher)
    with pytest.raises(RuntimeError):
        await worker.relay_once()

    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        pending = await outbox.fetch_unpublished()
    assert len(pending) == 1
