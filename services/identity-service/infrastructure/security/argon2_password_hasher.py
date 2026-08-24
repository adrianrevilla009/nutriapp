"""Argon2PasswordHasher — implements PasswordHasherPort.

argon2-cffi only, per docs/security-and-compliance.md ("Password hashing
via argon2 (preferred) or bcrypt. Never a custom scheme."). Never logs the
plaintext or the resulting hash.
"""
from __future__ import annotations

from argon2 import PasswordHasher as Argon2Lib
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from domain.value_objects.password import Password


class Argon2PasswordHasher:
    """Implements domain.ports.password_hasher_port.PasswordHasherPort."""

    def __init__(self) -> None:
        self._hasher = Argon2Lib()

    def hash(self, password: Password) -> str:
        return self._hasher.hash(password.plaintext)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            # Wrong password, or a malformed/foreign hash format — both
            # treated as a verification failure, never raised out of an
            # auth check (argon2-cffi's documented exception hierarchy).
            return False
