import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.user import User
from domain.services.registration_policy import EmailAlreadyRegisteredError
from domain.value_objects.email import Email
from infrastructure.persistence.postgres_user_repository import PostgresUserRepository


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


async def test_postgres_user_repository__save_then_get__round_trips(session):
    repo = PostgresUserRepository(session)
    user = User.register(Email("round@example.com"), "hashed")
    await repo.save(user)
    await session.commit()

    fetched = await repo.get_by_id(user.user_id)
    assert fetched is not None
    assert str(fetched.email) == "round@example.com"
    assert fetched.password_hash == "hashed"


async def test_postgres_user_repository__get_by_email_case_insensitive(session):
    repo = PostgresUserRepository(session)
    user = User.register(Email("MixedCase@Example.com"), "hashed")
    await repo.save(user)
    await session.commit()

    fetched = await repo.get_by_email(Email("mixedcase@example.com"))
    assert fetched is not None
    assert fetched.user_id == user.user_id


async def test_postgres_user_repository__duplicate_email__raises_domain_error_not_raw_db_error(
    session,
):
    repo = PostgresUserRepository(session)
    user1 = User.register(Email("dup@example.com"), "hashed")
    await repo.save(user1)
    await session.commit()

    user2 = User.register(Email("dup@example.com"), "hashed2")
    with pytest.raises(EmailAlreadyRegisteredError):
        await repo.save(user2)
