"""PostgresUserMetricsSnapshotRepository -- functional round-trip PLUS the
security-critical negative test required by test-plan section 2:
`user_metrics_snapshot`'s persisted row/schema must never contain a
`weight_kg`/`height_cm`/`age`/`sex` column at all (implementation plan
Addendum 1, security sub-addendum requirement 8). This is a schema-level
assertion (inspecting actual DB columns), not merely "the test didn't set
one" -- a genuine regression guard against ever re-adding a plaintext
biometric column to this table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.ports.user_metrics_snapshot_port import UserMetricsSnapshotMetadata
from infrastructure.persistence.models import UserMetricsSnapshotModel
from infrastructure.persistence.postgres_user_metrics_snapshot_repository import (
    PostgresUserMetricsSnapshotRepository,
)

FORBIDDEN_PLAINTEXT_BIOMETRIC_COLUMNS = {"weight_kg", "height_cm", "age", "sex"}


async def test_record_fetch_and_get_round_trip(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        repo = PostgresUserMetricsSnapshotRepository(session)
        assert await repo.get(user_id) is None
        await repo.record_fetch(
            UserMetricsSnapshotMetadata(
                user_id=user_id,
                last_fetched_at=now,
                formula_version="2026.1",
                sex_constant_used="MALE",
            )
        )
        await session.commit()

    async with session_factory() as session:
        repo = PostgresUserMetricsSnapshotRepository(session)
        snapshot = await repo.get(user_id)
        assert snapshot is not None
        assert snapshot.formula_version == "2026.1"
        assert snapshot.sex_constant_used == "MALE"


async def test_repeated_fetch_upserts_not_appends(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresUserMetricsSnapshotRepository(session)
        await repo.record_fetch(
            UserMetricsSnapshotMetadata(
                user_id=user_id,
                last_fetched_at=datetime.now(timezone.utc),
                formula_version="2026.1",
                sex_constant_used="MALE",
            )
        )
        await repo.record_fetch(
            UserMetricsSnapshotMetadata(
                user_id=user_id,
                last_fetched_at=datetime.now(timezone.utc),
                formula_version="2026.2",
                sex_constant_used="FEMALE",
            )
        )
        await session.commit()

    async with session_factory() as session:
        repo = PostgresUserMetricsSnapshotRepository(session)
        snapshot = await repo.get(user_id)
        assert snapshot.formula_version == "2026.2"
        assert snapshot.sex_constant_used == "FEMALE"


def test_schema_never_contains_a_plaintext_biometric_column():
    """SECURITY-CRITICAL negative test (test-plan section 2). Inspects the
    ORM model's actual mapped columns -- not just this test's own usage --
    so a future PR that adds `weight_kg` etc. back to
    `UserMetricsSnapshotModel` fails this test immediately."""
    mapper = inspect(UserMetricsSnapshotModel)
    column_names = {column.key for column in mapper.columns}

    overlap = column_names & FORBIDDEN_PLAINTEXT_BIOMETRIC_COLUMNS
    assert overlap == set(), (
        f"user_metrics_snapshot must never store plaintext biometric fields; "
        f"found forbidden column(s): {overlap}"
    )
    assert column_names == {"user_id", "last_fetched_at", "formula_version", "sex_constant_used"}
