"""PyzbarBarcodeDecoder -- against the locally-generated barcode fixture
images (test-plan section 2/7), never sourced from any external site.
Requires the `libzbar0` system shared library at test-run time (see
README.md's "Running locally" section) -- CI's runner installs it, as
does the service's own Dockerfile.
"""

from __future__ import annotations

import os

from domain.value_objects.barcode import Barcode
from infrastructure.recognition.pyzbar_barcode_decoder import PyzbarBarcodeDecoder

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "barcode_images")


def _read(name: str) -> bytes:
    with open(os.path.join(_FIXTURES_DIR, name), "rb") as f:
        return f.read()


def test_decodes_known_matched_barcode():
    decoder = PyzbarBarcodeDecoder()
    result = decoder.decode(_read("known_matched_gtin13.png"))
    assert result == Barcode("4006381333931")


def test_decodes_known_unmatched_barcode():
    decoder = PyzbarBarcodeDecoder()
    result = decoder.decode(_read("known_unmatched_gtin13.png"))
    assert result == Barcode("5901234123457")


def test_non_barcode_image_returns_none_not_an_exception():
    decoder = PyzbarBarcodeDecoder()
    result = decoder.decode(_read("not_a_barcode.png"))
    assert result is None


def test_garbage_bytes_return_none_not_an_exception():
    decoder = PyzbarBarcodeDecoder()
    result = decoder.decode(b"not-an-image-at-all")
    assert result is None
