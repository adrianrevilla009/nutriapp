from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.dto.user_metrics_snapshot_dto import UserMetricsSnapshotDTO
from domain.ports.user_metrics_snapshot_port import UserMetricsSnapshotMetadata


def test_from_metadata_maps_fields_without_any_plaintext_biometric_value():
    metadata = UserMetricsSnapshotMetadata(
        user_id=uuid.uuid4(),
        last_fetched_at=datetime.now(timezone.utc),
        formula_version="2026.1",
        sex_constant_used="MALE",
    )
    dto = UserMetricsSnapshotDTO.from_metadata(metadata)

    assert dto.user_id == metadata.user_id
    assert dto.formula_version == "2026.1"
    assert dto.sex_constant_used == "MALE"
    assert not hasattr(dto, "weight_kg")
