"""Status vocabulary for a barcode-decode-and-lookup attempt
(implementation plan section 1, acceptance criterion 3 / test-plan
section 1's `DecodeBarcodeHandler` cases).

- "matched": the barcode decoded successfully and catalog-service
  returned a matching product.
- "no_match": either the image had no decodable barcode, or the decoded
  barcode has no matching product in the catalog -- both are an explicit,
  honest "no match," never a guess.
- "unavailable": catalog-service's internal lookup call failed (circuit
  open, retries exhausted, timeout) -- manual entry is the fallback.
"""

from __future__ import annotations

from typing import Literal

BarcodeLookupStatus = Literal["matched", "no_match", "unavailable"]
