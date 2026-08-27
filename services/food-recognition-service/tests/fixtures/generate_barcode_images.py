"""One-off utility to (re)generate tests/fixtures/barcode_images/*.png.

Not run automatically by the test suite or CI -- the generated PNGs are
committed as fixtures (test-plan section 7). Re-run manually
(`uv run python tests/fixtures/generate_barcode_images.py`) only if the
fixture set needs to change. Uses `python-barcode` to encode a handful of
known, valid (GS1 check-digit-verified) GTIN-13 test values -- never
sourced from any external site or real product photo
(`external-data-ethics` SKILL.md).
"""

from __future__ import annotations

import io
import os

import barcode
from barcode.writer import ImageWriter
from PIL import Image

_OUT_DIR = os.path.join(os.path.dirname(__file__), "barcode_images")

# Arbitrary, valid (check-digit-correct) GTIN-13 values -- not tied to any
# real product. "known_unmatched" is deliberately a different value so the
# CatalogLookupClient integration test's fixture HTTP server can return a
# genuine 404 for it while returning a match for "known_matched".
_CODES = {
    "known_matched_gtin13": "4006381333931",
    "known_unmatched_gtin13": "5901234123457",
}


def main() -> None:
    os.makedirs(_OUT_DIR, exist_ok=True)
    for name, value in _CODES.items():
        ean = barcode.get("ean13", value, writer=ImageWriter())
        buf = io.BytesIO()
        ean.write(buf, options={"write_text": False})
        with open(os.path.join(_OUT_DIR, f"{name}.png"), "wb") as f:
            f.write(buf.getvalue())

    # A plain, non-barcode image -- must decode to None, not raise.
    plain = Image.new("RGB", (200, 200), color=(120, 180, 90))
    plain.save(os.path.join(_OUT_DIR, "not_a_barcode.png"))


if __name__ == "__main__":
    main()
