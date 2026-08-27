import uuid

import pytest

from application.errors import ProductNotFoundError
from application.queries.get_product_by_barcode import (
    GetProductByBarcodeHandler,
    GetProductByBarcodeQuery,
)
from domain.entities.product import Product
from domain.value_objects.barcode import Barcode
from tests.fixtures.factories import FakeProductRepository, make_raw_record


async def test_get_existing_product_by_barcode():
    products = FakeProductRepository()
    record = make_raw_record(barcode=Barcode("5901234123457"))
    product = Product.from_first_record(product_id=uuid.uuid4(), record=record)
    products.by_id[product.product_id] = product
    handler = GetProductByBarcodeHandler(products)

    result = await handler.handle(GetProductByBarcodeQuery(barcode=Barcode("5901234123457")))

    assert result.product_id == product.product_id
    assert result.barcode == Barcode("5901234123457")


async def test_get_product_by_unknown_barcode_raises_not_found():
    products = FakeProductRepository()
    handler = GetProductByBarcodeHandler(products)

    query = GetProductByBarcodeQuery(barcode=Barcode("5901234123457"))
    with pytest.raises(ProductNotFoundError):
        await handler.handle(query)
