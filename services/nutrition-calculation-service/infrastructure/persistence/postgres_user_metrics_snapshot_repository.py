"""PostgresUserMetricsSnapshotRepository -- implements
UserMetricsSnapshotPort. Metadata only (implementation plan Addendum 1,
security sub-addendum requirement 8) -- see
infrastructure/persistence/models.py's UserMetricsSnapshotModel docstring
and the schema-level negative test guarding this."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domain.ports.user_metrics_snapshot_port import UserMetricsSnapshotMetadata
from infrastructure.persistence.models import UserMetricsSnapshotModel


def _to_domain(row: UserMetricsSnapshotModel) -> UserMetricsSnapshotMetadata:
    return UserMetricsSnapshotMetadata(
        user_id=row.user_id,
        last_fetched_at=row.last_fetched_at,
        formula_version=row.formula_version,
        sex_constant_used=row.sex_constant_used,
    )


class PostgresUserMetricsSnapshotRepository:
    """Implements domain.ports.user_metrics_snapshot_port.UserMetricsSnapshotPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_fetch(self, metadata: UserMetricsSnapshotMetadata) -> None:
        row = await self._session.get(UserMetricsSnapshotModel, metadata.user_id)
        if row is None:
            row = UserMetricsSnapshotModel(user_id=metadata.user_id)
            self._session.add(row)
        row.last_fetched_at = metadata.last_fetched_at
        row.formula_version = metadata.formula_version
        row.sex_constant_used = metadata.sex_constant_used
        await self._session.flush()

    async def get(self, user_id: uuid.UUID) -> UserMetricsSnapshotMetadata | None:
        row = await self._session.get(UserMetricsSnapshotModel, user_id)
        return _to_domain(row) if row is not None else None
