"""User aggregate root.

Zero framework imports (ADR-0001). Password hashing itself is an
infrastructure concern (PasswordHasherPort); this aggregate only ever
holds/compares already-computed hashes, never plaintext.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from domain.value_objects.email import Email
from domain.value_objects.role import Role

FAILED_LOGIN_LOCK_THRESHOLD = 5


class UserStatus(str, Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"


class AlreadyVerifiedError(Exception):
    """Raised when verify_email() is called on an already-ACTIVE user."""


class EmailNotVerifiedError(Exception):
    """Raised on a login attempt against a PENDING_VERIFICATION user."""


class AccountLockedError(Exception):
    """Raised on a login attempt against a LOCKED user, regardless of password."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class User:
    """A registered user. Aggregate root for authentication/authorization state."""

    user_id: uuid.UUID
    email: Email
    password_hash: str
    status: UserStatus
    roles: frozenset[Role]
    created_at: datetime
    failed_login_attempts: int = 0
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    known_device_fingerprints: set[str] = field(default_factory=set)

    @classmethod
    def register(cls, email: Email, password_hash: str) -> User:
        """Factory for a brand-new registration. Always starts PENDING_VERIFICATION."""
        return cls(
            user_id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            status=UserStatus.PENDING_VERIFICATION,
            roles=frozenset({Role.USER}),
            created_at=_utcnow(),
        )

    def verify_email(self) -> None:
        if self.status == UserStatus.ACTIVE:
            raise AlreadyVerifiedError("User email is already verified.")
        self.status = UserStatus.ACTIVE

    def ensure_can_attempt_login(self) -> None:
        """Raises if this account must not be allowed to attempt a login at all,
        independent of whether the presented password is correct."""
        if self.status == UserStatus.LOCKED:
            raise AccountLockedError("Account is locked.")
        if self.status == UserStatus.PENDING_VERIFICATION:
            raise EmailNotVerifiedError("Email address is not verified.")

    def record_login_failure(self) -> None:
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= FAILED_LOGIN_LOCK_THRESHOLD:
            self.status = UserStatus.LOCKED

    def record_login_success(self) -> None:
        self.failed_login_attempts = 0
        self.last_login_at = _utcnow()

    def change_password(self, new_password_hash: str) -> None:
        self.password_hash = new_password_hash
        self.password_changed_at = _utcnow()

    def assign_role(self, role: Role) -> None:
        self.roles = self.roles | {role}

    def revoke_role(self, role: Role) -> None:
        self.roles = self.roles - {role}

    def is_known_device(self, fingerprint_hash: str) -> bool:
        return fingerprint_hash in self.known_device_fingerprints

    def is_first_login(self) -> bool:
        return len(self.known_device_fingerprints) == 0

    def remember_device(self, fingerprint_hash: str) -> None:
        self.known_device_fingerprints.add(fingerprint_hash)
