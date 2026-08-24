"""GET /.well-known/jwks.json — public key distribution per ADR-0022's
Open Host Service pattern. Every other service fetches and caches this
(with rotation in mind) to verify access tokens locally."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from infrastructure.composition_root import Container
from infrastructure.http.dependencies import get_container

router = APIRouter(tags=["jwks"])


@router.get(
    "/.well-known/jwks.json",
    summary="JWK Set for verifying identity-service access tokens",
    description="Public key material only (RFC 7517). No synchronous call back to "
    "identity-service is needed to validate a token once this is cached.",
)
async def jwks(container: Container = Depends(get_container)) -> dict:
    return container.token_issuer.get_jwks()
