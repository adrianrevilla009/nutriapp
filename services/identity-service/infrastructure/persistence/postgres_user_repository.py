"""PostgresUserRepository — implements UserRepositoryPort."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.user import User, UserStatus
from domain.services.registration_policy import EmailAlreadyRegisteredError
from domain.value_objects.email import Email
from domain.value_objects.role import Role
from infrastructure.persistence.models import UserModel


def _to_domain(row: UserModel) -> User:
    return User(
        user_id=row.id,
        email=Email(row.email),
        password_hash=row.password_hash,
        status=UserStatus(row.status),
        roles=frozenset(Role(r) for r in row.roles),
        created_at=row.created_at,
        failed_login_attempts=row.failed_login_attempts,
        last_login_at=row.last_login_at,
        password_changed_at=row.password_changed_at,
        known_device_fingerprints=set(row.known_device_fingerprints),
    )


def _apply_domain(row: UserModel, user: User) -> None:
    row.id = user.user_id
    row.email = str(user.email)
    row.password_hash = user.password_hash
    row.status = user.status.value
    row.roles = sorted(r.value for r in user.roles)
    row.failed_login_attempts = user.failed_login_attempts
    row.last_login_at = user.last_login_at
    row.password_changed_at = user.password_changed_at
    row.created_at = user.created_at
    row.known_device_fingerprints = sorted(user.known_device_fingerprints)


class PostgresUserRepository:
    """Implements domain.ports.user_repository_port.UserRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return _to_domain(row) if row else None

    async def get_by_email(self, email: Email) -> User | None:
        stmt = select(UserModel).where(func.lower(UserModel.email) == str(email))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def save(self, user: User) -> None:
        row = await self._session.get(UserModel, user.user_id)
        if row is None:
            row = UserModel(id=user.user_id)
            self._session.add(row)
        _apply_domain(row, user)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise EmailAlreadyRegisteredError(
                f"An account already exists for '{user.email}'."
            ) from exc
