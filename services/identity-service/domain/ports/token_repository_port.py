from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.token import RefreshToken, SecretReferenceToken, SecretTokenKind


class TokenRepositoryPort(Protocol):
    # Refresh tokens
    async def save_refresh_token(self, token: RefreshToken) -> None: ...

    async def get_refresh_token(self, token_id: uuid.UUID) -> RefreshToken | None: ...

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    async def revoke_all_refresh_tokens_for_user(self, user_id: uuid.UUID) -> None: ...

    # Secret-reference tokens (email verification / password reset)
    async def save_secret_token(self, token: SecretReferenceToken) -> None: ...

    async def get_secret_token(self, reference_id: uuid.UUID) -> SecretReferenceToken | None: ...

    async def get_latest_secret_token_for_user(
        self, user_id: uuid.UUID, kind: SecretTokenKind
    ) -> SecretReferenceToken | None: ...
