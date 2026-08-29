"""Shared FastAPI dependencies: request-scoped DB session, correlation id,
authenticated caller identity. Reuses the centralized JWT auth dependency
from packages/shared-contracts (commit 4248242, lazy container lookup per
commit 052a821), exactly as food-recognition-service already does."""

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
    return await shared_auth.get_authenticated_user_id(
        request, lambda: request.app.state.container.jwt_verifier
    )
