"""Role value object — v1 roles only, per ADR-0022 and docs/authorization-model.md.

Tokens carry roles, never raw permissions. Fine-grained per-resource
authorization stays in each owning service.
"""
from __future__ import annotations

from enum import Enum


class InvalidRoleError(ValueError):
    """Raised when an unknown role string is supplied."""


class Role(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"

    @classmethod
    def from_value(cls, value: str) -> Role:
        try:
            return cls(value)
        except ValueError as exc:
            raise InvalidRoleError(f"'{value}' is not a valid role.") from exc
