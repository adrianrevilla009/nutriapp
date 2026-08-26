import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.product import Product
from infrastructure.persistence.postgres_product_repository import PostgresProductRepository
from tests.fixtures.factories import make_raw_record

pytestmark = pytest.mark.usefixtures("db_engine")


async def _seed(db_engine, **overrides) -> Product:
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresProductRepository(session)
        record = make_raw_record(**overrides)
        product = Product.merge(existing=None, incoming=record).product
        await repo.save(product)
        await session.commit()
        return product


async def test_search_response_schema_matches_documented_contract(app_client, db_engine):
    await _seed(db_engine, name="Contract Test Snack")

    response = await app_client.get(
        "/api/v1/catalog/products/search", params={"q": "Contract Test"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size"}
    assert body["total"] >= 1
    assert body["items"][0]["name"] == "Contract Test Snack"


async def test_unsupported_filter_value_returns_422_not_500(app_client, db_engine):
    response = await app_client.get(
        "/api/v1/catalog/products/search", params={"dietary_tags": "not-a-real-tag"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "UNSUPPORTED_FILTER"
