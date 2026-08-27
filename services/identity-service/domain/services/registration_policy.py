"""Registration domain policy.

A stateless domain service (no I/O) — the application layer is
responsible for fetching whatever data the policy needs (e.g. an existing
user by email) via a port, then handing it to this policy to decide.
"""

from __future__ import annotations

from domain.entities.user import User
from domain.value_objects.email import Email


class EmailAlreadyRegisteredError(Exception):
    """Raised when a registration is attempted for an email already on file."""


class RegistrationPolicy:
    @staticmethod
    def ensure_email_available(email: Email, existing_user: User | None) -> None:
        if existing_user is not None:
            raise EmailAlreadyRegisteredError(f"An account already exists for '{email}'.")
