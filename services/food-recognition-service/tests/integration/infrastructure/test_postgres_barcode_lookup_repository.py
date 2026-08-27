from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.barcode_lookup import BarcodeLookup
from infrastructure.persistence.postgres_barcode_lookup_repository import (
    PostgresBarcodeLookupRepository,
)

pytestmark = pytest.mark.usefixtures("db_engine")


async def test_round_trip_persistence_with_match(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    lookup_id = uuid.uuid4()
    product_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresBarcodeLookupRepository(session)
        lookup = BarcodeLookup(
            lookup_id=lookup_id,
            user_id=uuid.uuid4(),
            submitted_at=datetime.now(timezone.utc),
            decoded_barcode="4006381333931",
            matched_product_id=product_id,
            status="matched",
        )
        await repo.save(lookup)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresBarcodeLookupRepository(session)
        loaded = await repo.get_by_id(lookup_id)
        assert loaded is not None
        assert loaded.status == "matched"
        assert loaded.matched_product_id == product_id


async def test_round_trip_persistence_with_no_match(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    lookup_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresBarcodeLookupRepository(session)
        lookup = BarcodeLookup(
            lookup_id=lookup_id,
            user_id=uuid.uuid4(),
            submitted_at=datetime.now(timezone.utc),
            decoded_barcode=None,
            matched_product_id=None,
            status="no_match",
        )
        await repo.save(lookup)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresBarcodeLookupRepository(session)
        loaded = await repo.get_by_id(lookup_id)
        assert loaded is not None
        assert loaded.decoded_barcode is None
        assert loaded.matched_product_id is None
