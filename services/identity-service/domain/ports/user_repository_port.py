from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.user import User
from domain.value_objects.email import Email


class UserRepositoryPort(Protocol):
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...

    async def save(self, user: User) -> None: ...
