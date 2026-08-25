"""GetEvolutionTimelineQuery + handler -- powers the user details panel's
graphs (implementation plan acceptance criterion 7), reading the
profile_evolution read model rather than replaying events.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from application.dto.profile_dto import EvolutionEntryDTO
from domain.ports.data_encryption_port import DataEncryptionPort
from domain.ports.evolution_read_model_port import EvolutionReadModelPort

_CASTERS = {"weight_kg": float, "height": float, "age": int, "sex": str, "activity_level": str}


@dataclass(frozen=True, slots=True)
class GetEvolutionTimelineQuery:
    user_id: uuid.UUID
    metric: str
    from_ts: datetime | None = None
    to_ts: datetime | None = None


class GetEvolutionTimelineHandler:
    def __init__(
        self, evolution_read: EvolutionReadModelPort, encryption: DataEncryptionPort
    ) -> None:
        self._evolution_read = evolution_read
        self._encryption = encryption

    async def handle(self, query: GetEvolutionTimelineQuery) -> list[EvolutionEntryDTO]:
        rows = await self._evolution_read.get_evolution(
            query.user_id, query.metric, query.from_ts, query.to_ts
        )
        caster = _CASTERS.get(query.metric, str)
        entries: list[EvolutionEntryDTO] = []
        for row in rows:
            ciphertext = row["value"]
            plaintext = await self._encryption.decrypt(query.user_id, ciphertext)
            entries.append(
                EvolutionEntryDTO(
                    metric=row["metric"], value=caster(plaintext), recorded_at=row["recorded_at"]
                )
            )
        return entries
