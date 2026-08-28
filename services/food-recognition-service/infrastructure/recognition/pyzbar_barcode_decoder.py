"""PyzbarBarcodeDecoder -- implements BarcodeDecoderPort using `pyzbar`
(wrapping the system `libzbar` shared library), per implementation plan
section 1's technology choice. Pure, local, synchronous decode -- no
external call, no circuit breaker (implementation plan section 4).

Requires the `libzbar0` system shared library to be present at runtime
(installed via the service's Dockerfile / CI image, never bundled in the
Python wheel on Linux) -- see README.md's "Running locally" section.
"""

from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError
from pyzbar.pyzbar import decode as zbar_decode

from domain.value_objects.barcode import Barcode, InvalidBarcodeError


class PyzbarBarcodeDecoder:
    """Implements domain.ports.barcode_decoder_port.BarcodeDecoderPort."""

    def decode(self, image_bytes: bytes) -> Barcode | None:
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except UnidentifiedImageError:
            return None

        for result in zbar_decode(image):
            raw_value = result.data.decode("utf-8", errors="ignore")
            try:
                return Barcode(raw_value)
            except InvalidBarcodeError:
                # Decoded a symbol (e.g. a QR code, or a barcode that
                # fails GS1 check-digit validation) that isn't a usable
                # product barcode -- keep scanning the rest of the
                # results rather than failing the whole decode.
                continue
        return None
