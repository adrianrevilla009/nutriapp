"""Email value object.

Pure domain code — no framework imports (ADR-0001).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvalidEmailError(ValueError):
    """Raised when a string does not satisfy the domain-level email format rule."""


@dataclass(frozen=True, slots=True)
class Email:
    """An email address, normalized to lowercase.

    Domain-level format validation only (presence of '@' and a domain with a
    dot). Deliverability is not this layer's concern.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidEmailError("Email must not be empty.")
        normalized = self.value.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise InvalidEmailError(f"'{self.value}' is not a valid email address.")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
