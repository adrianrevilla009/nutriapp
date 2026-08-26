import uuid

import pytest

from application.errors import ProductNotFoundError
from application.queries.get_product_by_id import GetProductByIdHandler, GetProductByIdQuery
from domain.entities.product import Product
from tests.fixtures.factories import FakeProductRepository, make_raw_record


async def test_get_existing_product_by_id():
    products = FakeProductRepository()
    product = Product.from_first_record(product_id=uuid.uuid4(), record=make_raw_record())
    products.by_id[product.product_id] = product
    handler = GetProductByIdHandler(products)

    result = await handler.handle(GetProductByIdQuery(product_id=product.product_id))

    assert result.product_id == product.product_id


async def test_get_nonexistent_product_raises_not_found():
    products = FakeProductRepository()
    handler = GetProductByIdHandler(products)

    with pytest.raises(ProductNotFoundError):
        await handler.handle(GetProductByIdQuery(product_id=uuid.uuid4()))
