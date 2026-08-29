"""Shared FastAPI dependencies: correlation id, authenticated caller
identity. Reuses the centralized JWT auth dependency from
packages/shared-contracts, exactly as food-recognition-service and
notification-service already do.

Implementation plan section 3/9.2: this is a lightweight, local/dev
convenience only -- in a real deployment Kong already validates the JWT
signature at the edge before a request ever reaches this service; this
dependency exists so a request made directly against this service
(bypassing Kong, e.g. in docker-compose or a test) still gets a proper
401 instead of silently proceeding unauthenticated. It never
re-implements JWT verification logic of its own -- `JwtVerifier` is the
one shared implementation every service already uses."""

from __future__ import annotations

import uuid

from fastapi import Request
from shared_contracts.auth import dependencies as shared_auth

from infrastructure.composition_root import Container

get_correlation_id = shared_auth.get_correlation_id


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


async def get_authenticated_user_id(request: Request) -> uuid.UUID:
    return await shared_auth.get_authenticated_user_id(
        request, lambda: request.app.state.container.jwt_verifier
    )
