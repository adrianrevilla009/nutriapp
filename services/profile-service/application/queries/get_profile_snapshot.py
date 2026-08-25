"""GetProfileSnapshotQuery + handler -- reads the profile_snapshot read
model (never replays the event stream on a read, per implementation plan
acceptance criterion 6). The read model's encrypted-field columns hold the
same ciphertext as the event store (contract-tested); this handler is the
one place that decrypts them back to plaintext for the authenticated
owner (api-conventions SKILL.md).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from application.dto.profile_dto import ProfileSnapshotDTO
from application.errors import ProfileNotFoundError
from domain.ports.data_encryption_port import DataEncryptionPort
from domain.ports.profile_snapshot_read_port import ProfileSnapshotReadPort

_ENCRYPTED_NUMERIC_FIELDS = ("weight_kg", "goal_target_value")
_ENCRYPTED_BODY_METRIC_FIELDS = {"height_cm": float, "age": int, "sex": str, "activity_level": str}


@dataclass(frozen=True, slots=True)
class GetProfileSnapshotQuery:
    user_id: uuid.UUID


class GetProfileSnapshotHandler:
    def __init__(
        self, snapshot_read: ProfileSnapshotReadPort, encryption: DataEncryptionPort
    ) -> None:
        self._snapshot_read = snapshot_read
        self._encryption = encryption

    async def handle(self, query: GetProfileSnapshotQuery) -> ProfileSnapshotDTO:
        row = await self._snapshot_read.get_snapshot(query.user_id)
        if row is None:
            raise ProfileNotFoundError("No profile exists yet for this user_id.")

        decrypted: dict[str, object] = {}
        for field_name in _ENCRYPTED_NUMERIC_FIELDS:
            ciphertext = row.get(field_name)
            decrypted[field_name] = (
                float(await self._encryption.decrypt(query.user_id, ciphertext))
                if ciphertext is not None
                else None
            )
        for field_name, caster in _ENCRYPTED_BODY_METRIC_FIELDS.items():
            ciphertext = row.get(field_name)
            decrypted[field_name] = (
                caster(await self._encryption.decrypt(query.user_id, ciphertext))
                if ciphertext is not None
                else None
            )

        goal_target_date = row.get("goal_target_date")
        return ProfileSnapshotDTO(
            user_id=query.user_id,
            consent_granted=bool(row.get("consent_granted", False)),
            weight_kg=decrypted["weight_kg"],
            height_cm=decrypted["height_cm"],
            age=decrypted["age"],
            sex=decrypted["sex"],
            activity_level=decrypted["activity_level"],
            goal_type=row.get("goal_type"),
            goal_target_value=decrypted["goal_target_value"],
            goal_target_date=date.fromisoformat(goal_target_date) if goal_target_date else None,
        )
