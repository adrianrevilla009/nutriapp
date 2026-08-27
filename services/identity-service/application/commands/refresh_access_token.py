"""RefreshAccessTokenCommand + handler.

No rotation-on-use for v1 (approved test-plan assumption) — the refresh
token itself is not reissued, only a new access token.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.security.token_generation import hash_secret
from domain.entities.token import TokenRevokedError
from domain.ports.token_issuer_port import TokenIssuerPort
from domain.ports.token_repository_port import TokenRepositoryPort
from domain.ports.user_repository_port import UserRepositoryPort


@dataclass(frozen=True, slots=True)
class RefreshAccessTokenCommand:
    refresh_token: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RefreshAccessTokenResult:
    access_token: str
    user_id: uuid.UUID


class RefreshAccessTokenHandler:
    def __init__(
        self,
        token_repository: TokenRepositoryPort,
        user_repository: UserRepositoryPort,
        token_issuer: TokenIssuerPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._tokens = token_repository
        self._users = user_repository
        self._token_issuer = token_issuer
        self._now_fn = now_fn

    async def handle(self, command: RefreshAccessTokenCommand) -> RefreshAccessTokenResult:
        token = await self._tokens.get_refresh_token_by_hash(hash_secret(command.refresh_token))
        if token is None:
            raise TokenRevokedError("Refresh token is invalid.")

        token.ensure_usable(self._now_fn())

        user = await self._users.get_by_id(token.user_id)
        if user is None:
            raise TokenRevokedError("Refresh token is invalid.")

        access_token = self._token_issuer.issue_access_token(user.user_id, user.roles)
        return RefreshAccessTokenResult(access_token=access_token, user_id=user.user_id)
