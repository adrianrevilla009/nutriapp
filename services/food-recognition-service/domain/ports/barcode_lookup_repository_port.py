from __future__ import annotations

from typing import Protocol

from domain.entities.barcode_lookup import BarcodeLookup


class BarcodeLookupRepositoryPort(Protocol):
    async def save(self, lookup: BarcodeLookup) -> None: ...
