"""UserMetricsSnapshotPort -- metadata-only record of the last successful
`ProfileRevealPort` fetch for a user (implementation plan Addendum 1,
security sub-addendum requirement 8): `last_fetched_at`, `formula_version`,
and (for traceability of `Sex.OTHER` handling) `sex_constant_used`.

**Never** the raw weight/height/age/sex plaintext -- that is fetched fresh
from `ProfileRevealPort` at each recompute and never persisted here, so
this table can never become a second, unencrypted, non-crypto-shreddable
copy of GDPR Article 9 special-category data outside profile-service's
erasure design (ADR-0023).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UserMetricsSnapshotMetadata:
    user_id: uuid.UUID
    last_fetched_at: datetime
    formula_version: str
    sex_constant_used: str | None


class UserMetricsSnapshotPort(Protocol):
    async def record_fetch(self, metadata: UserMetricsSnapshotMetadata) -> None: ...

    async def get(self, user_id: uuid.UUID) -> UserMetricsSnapshotMetadata | None: ...
