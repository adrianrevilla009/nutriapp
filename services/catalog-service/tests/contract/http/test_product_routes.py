import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.product import Product
from infrastructure.persistence.postgres_product_repository import PostgresProductRepository
from tests.fixtures.factories import make_raw_record

pytestmark = pytest.mark.usefixtures("db_engine")


async def test_get_existing_product_returns_200_with_full_shape(app_client, db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresProductRepository(session)
        record = make_raw_record()
        product = Product.merge(existing=None, incoming=record).product
        await repo.save(product)
        await session.commit()

    response = await app_client.get(f"/api/v1/catalog/products/{product.product_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == str(product.product_id)
    assert body["name"] == "Chocolate Bar"
    assert body["nutrition_per_100g"]["energy_kcal"] == 500


async def test_get_nonexistent_product_returns_404(app_client):
    response = await app_client.get(f"/api/v1/catalog/products/{uuid.uuid4()}")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "PRODUCT_NOT_FOUND"
