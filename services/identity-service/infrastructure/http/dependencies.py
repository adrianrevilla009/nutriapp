"""Shared FastAPI dependencies: request-scoped DB session, correlation id,
client context (api-conventions SKILL.md: every request propagates or
generates X-Correlation-Id)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.composition_root import Container


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    container: Container = request.app.state.container
    async with container.new_session() as session:
        yield session


async def get_audit_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Separate session bound to Container.audit_engine (privilege-restricted
    via SET ROLE at connect time) — never share this with get_session's
    session (see composition_root.build_repositories's docstring)."""
    container: Container = request.app.state.container
    async with container.new_audit_session() as audit_session:
        yield audit_session


def get_correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-Id") or str(uuid.uuid4())


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    return request.headers.get("User-Agent", "unknown")
