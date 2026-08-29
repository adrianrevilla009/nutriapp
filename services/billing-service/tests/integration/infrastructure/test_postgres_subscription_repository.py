import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.value_objects.stripe_ids import StripeSubscriptionId
from domain.value_objects.subscription_status import SubscriptionStatus
from infrastructure.persistence.postgres_subscription_repository import (
    PostgresSubscriptionRepository,
)
from tests.fixtures.factories import make_subscription

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_save_and_get_by_user_id_round_trip(session):
    repo = PostgresSubscriptionRepository(session)
    sub = make_subscription()
    await repo.save(sub)
    await session.commit()

    fetched = await repo.get_by_user_id(sub.user_id)
    assert fetched is not None
    assert fetched.subscription_id == sub.subscription_id
    assert fetched.status == SubscriptionStatus.active()


async def test_get_by_stripe_subscription_id(session):
    repo = PostgresSubscriptionRepository(session)
    sub = make_subscription(stripe_subscription_id=StripeSubscriptionId("sub_lookup_test"))
    await repo.save(sub)
    await session.commit()

    fetched = await repo.get_by_stripe_subscription_id(StripeSubscriptionId("sub_lookup_test"))
    assert fetched is not None
    assert fetched.user_id == sub.user_id


async def test_get_by_user_id_returns_none_when_absent(session):
    repo = PostgresSubscriptionRepository(session)
    result = await repo.get_by_user_id(__import__("uuid").uuid4())
    assert result is None


async def test_save_updates_existing_row(session):
    repo = PostgresSubscriptionRepository(session)
    sub = make_subscription()
    await repo.save(sub)
    await session.commit()

    cancelled = sub.cancel(sub.updated_at)
    await repo.save(cancelled)
    await session.commit()

    fetched = await repo.get_by_user_id(sub.user_id)
    assert fetched.cancel_at_period_end is True
