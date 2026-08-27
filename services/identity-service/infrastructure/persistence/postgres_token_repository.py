"""PostgresTokenRepository — implements TokenRepositoryPort.

Refresh tokens live in `refresh_tokens`; secret-reference tokens
(email verification / password reset) live in two kind-specific tables
per the implementation plan's migration file list.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.token import RefreshToken, SecretReferenceToken, SecretTokenKind
from infrastructure.persistence.models import (
    EmailVerificationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    _SecretTokenModelMixin,
)

# Both concrete models share every column via _SecretTokenModelMixin -- typed
# against the mixin (not the common `Base`, which mypy would otherwise widen
# this dict's value type to) so `.user_id`/`.created_at`/etc. stay visible on
# whichever concrete class this dict actually looks up.
_SECRET_TOKEN_MODELS: dict[SecretTokenKind, type[_SecretTokenModelMixin]] = {
    SecretTokenKind.EMAIL_VERIFICATION: EmailVerificationTokenModel,
    SecretTokenKind.PASSWORD_RESET: PasswordResetTokenModel,
}


def _refresh_to_domain(row: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        token_id=row.token_id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


def _secret_to_domain(row: _SecretTokenModelMixin, kind: SecretTokenKind) -> SecretReferenceToken:
    return SecretReferenceToken(
        reference_id=row.reference_id,
        user_id=row.user_id,
        kind=kind,
        secret_hash=row.secret_hash,
        created_at=row.created_at,
        expires_at=row.expires_at,
        raw_secret=row.raw_secret,
        revealed_at=row.revealed_at,
        used_at=row.used_at,
    )


class PostgresTokenRepository:
    """Implements domain.ports.token_repository_port.TokenRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_refresh_token(self, token: RefreshToken) -> None:
        row = await self._session.get(RefreshTokenModel, token.token_id)
        if row is None:
            row = RefreshTokenModel(token_id=token.token_id)
            self._session.add(row)
        row.user_id = token.user_id
        row.token_hash = token.token_hash
        row.created_at = token.created_at
        row.expires_at = token.expires_at
        row.revoked_at = token.revoked_at
        await self._session.flush()

    async def get_refresh_token(self, token_id: uuid.UUID) -> RefreshToken | None:
        row = await self._session.get(RefreshTokenModel, token_id)
        return _refresh_to_domain(row) if row else None

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _refresh_to_domain(row) if row else None

    async def revoke_all_refresh_tokens_for_user(self, user_id: uuid.UUID) -> None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.user_id == user_id)
        result = await self._session.execute(stmt)
        now = datetime.now(timezone.utc)
        for row in result.scalars():
            if row.revoked_at is None:
                row.revoked_at = now
        await self._session.flush()

    async def save_secret_token(self, token: SecretReferenceToken) -> None:
        model_cls = _SECRET_TOKEN_MODELS[token.kind]
        row = await self._session.get(model_cls, token.reference_id)
        if row is None:
            # Both concrete subclasses generate a mapped __init__ accepting
            # every mixin column as a kwarg -- mypy can't see that through
            # the mixin-typed `model_cls` alone.
            row = model_cls(reference_id=token.reference_id)  # type: ignore[call-arg]
            self._session.add(row)
        row.user_id = token.user_id
        row.secret_hash = token.secret_hash
        row.raw_secret = token.raw_secret
        row.created_at = token.created_at
        row.expires_at = token.expires_at
        row.revealed_at = token.revealed_at
        row.used_at = token.used_at
        await self._session.flush()

    async def get_secret_token(self, reference_id: uuid.UUID) -> SecretReferenceToken | None:
        for kind, model_cls in _SECRET_TOKEN_MODELS.items():
            row = await self._session.get(model_cls, reference_id)
            if row is not None:
                return _secret_to_domain(row, kind)
        return None

    async def get_latest_secret_token_for_user(
        self, user_id: uuid.UUID, kind: SecretTokenKind
    ) -> SecretReferenceToken | None:
        model_cls = _SECRET_TOKEN_MODELS[kind]
        stmt = (
            select(model_cls)
            .where(model_cls.user_id == user_id)
            .order_by(model_cls.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _secret_to_domain(row, kind) if row else None
