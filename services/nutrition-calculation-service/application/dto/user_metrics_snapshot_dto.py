from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.user_metrics_snapshot_port import UserMetricsSnapshotMetadata


@dataclass(frozen=True, slots=True)
class UserMetricsSnapshotDTO:
    user_id: uuid.UUID
    last_fetched_at: datetime
    formula_version: str
    sex_constant_used: str | None

    @classmethod
    def from_metadata(cls, metadata: UserMetricsSnapshotMetadata) -> UserMetricsSnapshotDTO:
        return cls(
            user_id=metadata.user_id,
            last_fetched_at=metadata.last_fetched_at,
            formula_version=metadata.formula_version,
            sex_constant_used=metadata.sex_constant_used,
        )
