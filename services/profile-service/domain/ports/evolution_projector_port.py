from __future__ import annotations

from typing import Protocol

from domain.events.base import DomainEvent


class EvolutionProjectorPort(Protocol):
    """Write-side of the profile_evolution read model -- one row per
    metric-recording event, correction events appended (never
    overwritten). See SnapshotProjectorPort's docstring for the
    synchronous-projection rationale."""

    async def apply(self, event: DomainEvent) -> None: ...
