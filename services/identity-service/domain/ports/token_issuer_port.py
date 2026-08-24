from __future__ import annotations

import uuid
from typing import Any, Protocol

from domain.value_objects.role import Role


class TokenIssuerPort(Protocol):
    def issue_access_token(self, user_id: uuid.UUID, roles: frozenset[Role]) -> str:
        """Issues a short-lived RS256 access token carrying user_id + roles (ADR-0022)."""
        ...

    def get_jwks(self) -> dict[str, Any]:
        """Returns the JWK Set (public key material only) for /.well-known/jwks.json."""
        ...
