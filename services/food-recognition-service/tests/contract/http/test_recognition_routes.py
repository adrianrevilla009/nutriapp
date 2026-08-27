"""Contract tests for the two public recognition routes (test-plan section
3): happy path plus every documented status branch, including the
`"uncertain"`/`"unavailable"`/`"no_match"` edge cases -- not just the
happy path.
"""

from __future__ import annotations

import uuid

import pytest

from domain.ports.catalog_lookup_port import CatalogLookupUnavailableError
from domain.ports.vision_recognition_port import VisionRecognitionUnavailableError
from domain.value_objects.barcode import Barcode
from tests.contract.http.conftest import auth_headers
from tests.fixtures.factories import make_candidate, make_catalog_product

pytestmark = pytest.mark.usefixtures("db_engine")

_IMAGE_FILE = ("photo.jpg", b"fake-image-bytes", "image/jpeg")


async def test_analyze_photo_detected(app_client, container):
    container.vision_adapter.candidates_to_return = [make_candidate(name="apple", confidence=0.9)]
    response = await app_client.post(
        "/api/v1/recognition/photos/analyze",
        files={"file": _IMAGE_FILE},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "detected"
    assert body["candidates"][0]["name"] == "apple"
    assert body["model_version"] == "claude-haiku-4-5"


async def test_analyze_photo_uncertain(app_client, container):
    container.vision_adapter.candidates_to_return = [
        make_candidate(name="mystery dish", confidence=0.2)
    ]
    response = await app_client.post(
        "/api/v1/recognition/photos/analyze",
        files={"file": _IMAGE_FILE},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "uncertain"
    assert len(body["candidates"]) == 1


async def test_analyze_photo_unavailable_on_provider_failure(app_client, container):
    container.vision_adapter.error_to_raise = VisionRecognitionUnavailableError("circuit open")
    response = await app_client.post(
        "/api/v1/recognition/photos/analyze",
        files={"file": _IMAGE_FILE},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 200  # a handled fallback, never a 5xx
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["candidates"] == []


async def test_analyze_photo_missing_file_is_422(app_client):
    response = await app_client.post(
        "/api/v1/recognition/photos/analyze", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 422


async def test_analyze_photo_unsupported_content_type_is_422(app_client):
    response = await app_client.post(
        "/api/v1/recognition/photos/analyze",
        files={"file": ("doc.txt", b"not an image", "text/plain")},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_IMAGE"


async def test_analyze_photo_requires_authentication(app_client):
    response = await app_client.post(
        "/api/v1/recognition/photos/analyze", files={"file": _IMAGE_FILE}
    )
    assert response.status_code == 401


async def test_decode_barcode_matched(app_client, container):
    barcode = Barcode("4006381333931")
    product = make_catalog_product()
    container.barcode_decoder.barcode_to_return = barcode
    container.catalog_lookup_client.product_to_return = product

    response = await app_client.post(
        "/api/v1/recognition/barcodes/decode",
        files={"file": _IMAGE_FILE},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "matched"
    assert body["product"]["product_id"] == str(product.product_id)


async def test_decode_barcode_no_match_for_undecodable_image(app_client, container):
    container.barcode_decoder.barcode_to_return = None
    response = await app_client.post(
        "/api/v1/recognition/barcodes/decode",
        files={"file": _IMAGE_FILE},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_match"
    assert body["product"] is None


async def test_decode_barcode_no_match_for_unmatched_barcode(app_client, container):
    container.barcode_decoder.barcode_to_return = Barcode("5901234123457")
    container.catalog_lookup_client.product_to_return = None
    response = await app_client.post(
        "/api/v1/recognition/barcodes/decode",
        files={"file": _IMAGE_FILE},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "no_match"


async def test_decode_barcode_unavailable_on_catalog_failure(app_client, container):
    container.barcode_decoder.barcode_to_return = Barcode("4006381333931")
    container.catalog_lookup_client.error_to_raise = CatalogLookupUnavailableError("circuit open")
    response = await app_client.post(
        "/api/v1/recognition/barcodes/decode",
        files={"file": _IMAGE_FILE},
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


async def test_decode_barcode_malformed_request_is_422(app_client):
    response = await app_client.post(
        "/api/v1/recognition/barcodes/decode", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 422
