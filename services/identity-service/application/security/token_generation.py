"""Opaque-secret generation/hashing helpers shared by the auth command
handlers.

Not password hashing (that's PasswordHasherPort / argon2, per
docs/security-and-compliance.md) — these are high-entropy random opaque
strings (refresh tokens, email-verification/password-reset secrets), for
which a fast cryptographic hash (SHA-256) is the correct, standard choice
for at-rest storage of the comparison hash.
"""
from __future__ import annotations

import hashlib
import secrets


def generate_opaque_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()
