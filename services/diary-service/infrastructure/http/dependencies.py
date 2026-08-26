"""Shared FastAPI dependencies: request-scoped DB session, correlation id,
authenticated caller identity.

Authentication (ADR-0022, docs/authorization-model.md section 2): every
request's `Authorization: Bearer <token>` header carries a RS256 JWT
issued by identity-service. This service verifies the token's signature
and expiry **locally**, via `shared_contracts.auth.jwt_verifier.JwtVerifier`
(`packages/shared-contracts/python/shared_contracts/auth/jwt_verifier.py`),
which fetches and caches identity-service's published JWKS
(`/.well-known/jwks.json`) -- no synchronous call back to identity-service
on every request, only on a JWKS cache miss/expiry. diary-service is this
verifier's third consumer after identity-service (issuer) and
profile-service, no new code needed in the shared package.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status
from shared_contracts.auth.jwt_verifier import (
    JwksCircuitOpenError,
    JwksFetchError,
    JwtVerificationError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.composition_root import Container

_BEARER_PREFIX = "Bearer "


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    container: Container = request.app.state.container
    async with container.new_session() as session:
        yield session


def get_correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-Id") or str(uuid.uuid4())


async def get_authenticated_user_id(request: Request) -> uuid.UUID:
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authenticated caller."
        )
    token = authorization[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authenticated caller."
        )

    container: Container = request.app.state.container
    try:
        principal = await container.jwt_verifier.verify(token)
    except JwtVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authenticated caller."
        ) from exc
    except (JwksFetchError, JwksCircuitOpenError) as exc:
        # Fail closed: if identity-service's public keys can't be fetched
        # (and the cache is empty/expired), a request cannot be
        # authenticated -- never silently accept an unverifiable token.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify authenticated caller.",
        ) from exc
    return principal.user_id
