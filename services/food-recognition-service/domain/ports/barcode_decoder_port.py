"""BarcodeDecoderPort -- decodes a barcode from raw image bytes. Concrete
adapter: `infrastructure.recognition.pyzbar_barcode_decoder.PyzbarBarcodeDecoder`.

Pure, local, no external call -- no circuit breaker needed (implementation
plan section 4: "matches `open_food_facts_source_adapter`'s 'no I/O'
precedent for why this stays synchronous internally even though the port
method it's called from is async"). Returns `None` (never raises) when
the image has no decodable barcode -- that is an ordinary, expected
outcome, not an error.
"""

from __future__ import annotations

from typing import Protocol

from domain.value_objects.barcode import Barcode


class BarcodeDecoderPort(Protocol):
    def decode(self, image_bytes: bytes) -> Barcode | None: ...
