"""Shared FastAPI dependencies: request-scoped DB session, correlation id,
authenticated caller identity.

Authentication (ADR-0022, docs/authorization-model.md section 2): every
request's `Authorization: Bearer <token>` header carries a RS256 JWT
issued by identity-service, verified locally via
`shared_contracts.auth.jwt_verifier.JwtVerifier` -- no synchronous call
back to identity-service on every request. The token-parsing/verification
logic itself now lives in `shared_contracts.auth.dependencies` (ADR-0022's
follow-up action); this module only wires this service's own `Container`
into it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Request
from shared_contracts.auth import dependencies as shared_auth
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.composition_root import Container

get_correlation_id = shared_auth.get_correlation_id


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    container: Container = request.app.state.container
    async with container.new_session() as session:
        yield session


async def get_authenticated_user_id(request: Request) -> uuid.UUID:
    container: Container = request.app.state.container
    return await shared_auth.get_authenticated_user_id(request, container.jwt_verifier)
