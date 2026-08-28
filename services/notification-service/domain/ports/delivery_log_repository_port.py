"""DeliveryLogRepositoryPort -- Postgres adapter:
postgres_delivery_log_repository.py."""

from __future__ import annotations

from typing import Protocol

from domain.entities.delivery_log_record import DeliveryLogRecord


class DeliveryLogRepositoryPort(Protocol):
    async def record(self, entry: DeliveryLogRecord) -> None: ...
