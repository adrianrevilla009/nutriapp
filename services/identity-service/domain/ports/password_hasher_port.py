from __future__ import annotations

from typing import Protocol

from domain.value_objects.password import Password


class PasswordHasherPort(Protocol):
    def hash(self, password: Password) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...
