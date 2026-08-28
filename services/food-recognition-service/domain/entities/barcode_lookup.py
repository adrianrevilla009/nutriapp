"""BarcodeLookup -- an append-only audit record of one barcode
decode-and-lookup attempt (implementation plan section 2). No domain
event is published for this record (implementation plan section 1,
acceptance criterion 4's rationale: either the barcode matched a product
or it didn't -- no ambiguity to resolve downstream), it exists purely for
audit/traceability.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.barcode_lookup_status import BarcodeLookupStatus


@dataclass(frozen=True, slots=True)
class BarcodeLookup:
    lookup_id: uuid.UUID
    user_id: uuid.UUID
    submitted_at: datetime
    decoded_barcode: str | None
    matched_product_id: uuid.UUID | None
    status: BarcodeLookupStatus
