from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.photo_analysis import PhotoAnalysis
from infrastructure.persistence.postgres_photo_analysis_repository import (
    PostgresPhotoAnalysisRepository,
)
from tests.fixtures.factories import make_candidate

pytestmark = pytest.mark.usefixtures("db_engine")


async def test_round_trip_persistence(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    analysis_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresPhotoAnalysisRepository(session)
        analysis = PhotoAnalysis(
            analysis_id=analysis_id,
            user_id=uuid.uuid4(),
            submitted_at=datetime.now(timezone.utc),
            candidates=[make_candidate(name="apple"), make_candidate(name="banana")],
            model_version="claude-haiku-4-5",
            status="detected",
            correlation_id="corr-1",
        )
        await repo.save(analysis)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresPhotoAnalysisRepository(session)
        loaded = await repo.get_by_id(analysis_id)
        assert loaded is not None
        assert loaded.status == "detected"
        assert [c.name for c in loaded.candidates] == ["apple", "banana"]
        assert loaded.model_version == "claude-haiku-4-5"


async def test_get_by_id_returns_none_when_missing(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = PostgresPhotoAnalysisRepository(session)
        assert await repo.get_by_id(uuid.uuid4()) is None
