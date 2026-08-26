import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.product import Product
from domain.value_objects.barcode import Barcode
from infrastructure.persistence.postgres_product_repository import PostgresProductRepository
from tests.fixtures.factories import make_raw_record

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture()
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_upsert_by_dedup_key_round_trip(session):
    repo = PostgresProductRepository(session)
    record = make_raw_record(barcode=Barcode("5901234123457"))
    product = Product.merge(existing=None, incoming=record).product
    await repo.save(product)
    await session.commit()

    fetched = await repo.get_by_barcode(Barcode("5901234123457"))
    assert fetched is not None
    assert fetched.product_id == product.product_id

    # Update same barcode — confirm single row (upsert, not insert).
    updated_record = make_raw_record(
        barcode=Barcode("5901234123457"),
        name="Updated Name",
        observed_at=datetime.now(timezone.utc),
    )
    merge_result = Product.merge(existing=fetched, incoming=updated_record)
    await repo.save(merge_result.product)
    await session.commit()

    refetched = await repo.get_by_barcode(Barcode("5901234123457"))
    assert refetched.name == "Updated Name"
    assert refetched.product_id == product.product_id


async def test_two_products_with_no_barcode_never_collide(session):
    repo = PostgresProductRepository(session)
    record_a = make_raw_record(barcode=None, source_product_id="off-a", name="Same Name")
    record_b = make_raw_record(barcode=None, source_product_id="off-b", name="Same Name")

    product_a = Product.merge(existing=None, incoming=record_a).product
    product_b = Product.merge(existing=None, incoming=record_b).product
    await repo.save(product_a)
    await repo.save(product_b)
    await session.commit()

    assert product_a.product_id != product_b.product_id
    fetched_a = await repo.get_by_id(product_a.product_id)
    fetched_b = await repo.get_by_id(product_b.product_id)
    assert fetched_a is not None and fetched_b is not None
    assert fetched_a.product_id != fetched_b.product_id


async def test_get_by_source_reference(session):
    repo = PostgresProductRepository(session)
    record = make_raw_record(barcode=None, source_product_id="off-xyz")
    product = Product.merge(existing=None, incoming=record).product
    await repo.save(product)
    await session.commit()

    fetched = await repo.get_by_source_reference("open_food_facts", "off-xyz")
    assert fetched is not None
    assert fetched.product_id == product.product_id


async def test_get_by_id_missing_returns_none(session):
    repo = PostgresProductRepository(session)
    assert await repo.get_by_id(uuid.uuid4()) is None
