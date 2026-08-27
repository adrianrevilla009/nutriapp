import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.product import Product
from domain.events.product_catalogued import build_product_catalogued_event
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_product_repository import PostgresProductRepository
from tests.fixtures.factories import make_raw_record

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_enqueue_and_fetch_unpublished(session):
    repo = PostgresProductRepository(session)
    product = Product.merge(existing=None, incoming=make_raw_record()).product
    await repo.save(product)

    outbox = PostgresOutboxRepository(session)
    event = build_product_catalogued_event(product=product, correlation_id="c1")
    await outbox.enqueue(event)
    await session.commit()

    pending = await outbox.fetch_unpublished()
    assert len(pending) == 1
    assert pending[0].event_type == "ProductCatalogued"


async def test_mark_published_removes_from_unpublished(session):
    repo = PostgresProductRepository(session)
    product = Product.merge(existing=None, incoming=make_raw_record()).product
    await repo.save(product)

    outbox = PostgresOutboxRepository(session)
    event = build_product_catalogued_event(product=product, correlation_id="c1")
    await outbox.enqueue(event)
    await session.commit()

    await outbox.mark_published(event.event_id)
    await session.commit()

    pending = await outbox.fetch_unpublished()
    assert pending == []
