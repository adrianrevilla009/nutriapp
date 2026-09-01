"""FastAPI dependency providers for social-service's own routes:
request-scoped DB session, inbound correlation id, and the authenticated
caller's user id.

Authentication (ADR-0022, docs/authorization-model.md section 2): every
route's `Authorization: Bearer <token>` header carries an RS256 JWT
issued by identity-service, verified LOCALLY via
`shared_contracts.auth.jwt_verifier.JwtVerifier` -- no synchronous call
back to identity-service on every request, only on a JWKS cache
miss/expiry."""

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
_MISSING_CALLER_DETAIL = "Missing authenticated caller."


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    container = get_container(request)
    async with container.new_session() as session:
        yield session


def get_correlation_id(request: Request) -> str:
    incoming = request.headers.get("X-Correlation-Id")
    return incoming if incoming else str(uuid.uuid4())


def _extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization") or ""
    if not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_MISSING_CALLER_DETAIL)

    token = authorization.removeprefix(_BEARER_PREFIX).strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_MISSING_CALLER_DETAIL)
    return token


async def get_authenticated_user_id(request: Request) -> uuid.UUID:
    token = _extract_bearer_token(request)
    container = get_container(request)

    try:
        principal = await container.jwt_verifier.verify(token)
    except JwtVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authenticated caller."
        ) from exc
    except (JwksFetchError, JwksCircuitOpenError) as exc:
        # Fail closed -- never silently accept a token we couldn't verify.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify authenticated caller.",
        ) from exc

    return principal.user_id
