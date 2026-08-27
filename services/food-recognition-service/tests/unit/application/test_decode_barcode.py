import inspect
import uuid

import pytest

from application.commands.decode_barcode import DecodeBarcodeCommand, DecodeBarcodeHandler
from application.errors import InvalidImageError
from domain.ports.catalog_lookup_port import CatalogLookupUnavailableError
from domain.value_objects.barcode import Barcode
from tests.fixtures.factories import (
    FakeBarcodeDecoderPort,
    FakeBarcodeLookupRepository,
    FakeCatalogLookupPort,
    make_catalog_product,
)

_KNOWN_BARCODE = Barcode("4006381333931")


def _command(image_bytes: bytes = b"fake-image-bytes") -> DecodeBarcodeCommand:
    return DecodeBarcodeCommand(
        user_id=uuid.uuid4(), image_bytes=image_bytes, correlation_id="corr-1"
    )


async def test_known_barcode_with_catalog_match_returns_matched_product():
    product = make_catalog_product()
    decoder = FakeBarcodeDecoderPort(barcode_to_return=_KNOWN_BARCODE)
    catalog = FakeCatalogLookupPort(product_to_return=product)
    repository = FakeBarcodeLookupRepository()
    handler = DecodeBarcodeHandler(decoder, catalog, repository)

    result = await handler.handle(_command())

    assert result.status == "matched"
    assert result.product is product
    assert repository.saved[0].matched_product_id == product.product_id
    assert repository.saved[0].decoded_barcode == str(_KNOWN_BARCODE)


async def test_known_barcode_with_no_catalog_match():
    decoder = FakeBarcodeDecoderPort(barcode_to_return=_KNOWN_BARCODE)
    catalog = FakeCatalogLookupPort(product_to_return=None)
    repository = FakeBarcodeLookupRepository()
    handler = DecodeBarcodeHandler(decoder, catalog, repository)

    result = await handler.handle(_command())

    assert result.status == "no_match"
    assert result.product is None
    assert repository.saved[0].matched_product_id is None


async def test_undecodable_image_never_calls_catalog_lookup():
    decoder = FakeBarcodeDecoderPort(barcode_to_return=None)
    catalog = FakeCatalogLookupPort(product_to_return=make_catalog_product())
    repository = FakeBarcodeLookupRepository()
    handler = DecodeBarcodeHandler(decoder, catalog, repository)

    result = await handler.handle(_command())

    assert result.status == "no_match"
    assert result.product is None
    assert catalog.call_count == 0
    assert repository.saved[0].decoded_barcode is None


async def test_catalog_lookup_unavailable_is_unavailable_with_no_exception():
    decoder = FakeBarcodeDecoderPort(barcode_to_return=_KNOWN_BARCODE)
    catalog = FakeCatalogLookupPort(error_to_raise=CatalogLookupUnavailableError("circuit open"))
    repository = FakeBarcodeLookupRepository()
    handler = DecodeBarcodeHandler(decoder, catalog, repository)

    result = await handler.handle(_command())

    assert result.status == "unavailable"
    assert result.product is None
    assert repository.saved[0].status == "unavailable"


async def test_empty_image_raises_invalid_image_error():
    decoder = FakeBarcodeDecoderPort(barcode_to_return=_KNOWN_BARCODE)
    catalog = FakeCatalogLookupPort(product_to_return=make_catalog_product())
    handler = DecodeBarcodeHandler(decoder, catalog, FakeBarcodeLookupRepository())
    with pytest.raises(InvalidImageError):
        await handler.handle(_command(image_bytes=b""))


def test_constructor_never_accepts_a_diary_service_port():
    params = inspect.signature(DecodeBarcodeHandler.__init__).parameters
    assert not any("diary" in name.lower() for name in params)
