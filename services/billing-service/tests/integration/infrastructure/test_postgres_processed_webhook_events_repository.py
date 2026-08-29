import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_processed_webhook_events_repository import (
    PostgresProcessedWebhookEventsRepository,
)

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_not_processed_by_default(session):
    repo = PostgresProcessedWebhookEventsRepository(session)
    assert await repo.is_processed("evt_unseen") is False


async def test_mark_processed_then_is_processed_true(session):
    repo = PostgresProcessedWebhookEventsRepository(session)
    await repo.mark_processed("evt_seen")
    await session.commit()
    assert await repo.is_processed("evt_seen") is True


async def test_mark_processed_twice_is_idempotent(session):
    repo = PostgresProcessedWebhookEventsRepository(session)
    await repo.mark_processed("evt_dup")
    await repo.mark_processed("evt_dup")
    await session.commit()
    assert await repo.is_processed("evt_dup") is True
