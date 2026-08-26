"""Shared FastAPI dependencies: request-scoped DB session, correlation id
(api-conventions SKILL.md: every request propagates or generates
X-Correlation-Id)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.composition_root import Container


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    container: Container = request.app.state.container
    async with container.new_session() as session:
        yield session


def get_correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
