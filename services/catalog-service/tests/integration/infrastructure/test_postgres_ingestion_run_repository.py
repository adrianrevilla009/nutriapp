import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from application.jobs.run_open_food_facts_ingestion import IngestionRunSummary
from infrastructure.persistence.postgres_ingestion_run_repository import (
    PostgresIngestionRunRepository,
)

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture()
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_start_and_finish_records_summary(session):
    repo = PostgresIngestionRunRepository(session)
    run_id = await repo.start("open_food_facts")
    await session.commit()

    summary = IngestionRunSummary(
        source="open_food_facts", items_seen=10, items_added=7, items_updated=2, items_skipped=1
    )
    await repo.finish(run_id, summary)
    await session.commit()

    from infrastructure.persistence.models import IngestionRunModel

    row = await session.get(IngestionRunModel, run_id)
    assert row.status == "completed"
    assert row.items_added == 7
    assert row.finished_at is not None


async def test_finish_on_unknown_run_id_is_a_no_op(session):
    import uuid

    repo = PostgresIngestionRunRepository(session)
    await repo.finish(uuid.uuid4(), IngestionRunSummary(source="usda_fdc"))
    # No exception raised — nothing to assert beyond "didn't crash".
