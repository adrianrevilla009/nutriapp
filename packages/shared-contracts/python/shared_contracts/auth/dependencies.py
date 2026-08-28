"""Generic FastAPI authentication dependency built on top of `JwtVerifier`
-- the "verify the Bearer token, map failures to 401" logic that was
byte-for-byte identical in every service's own
`infrastructure/http/dependencies.py` (ADR-0022's follow-up actions
flagged this as a `packages/shared-contracts` candidate; centralizing it
here is what that follow-up meant).

Each service's own `dependencies.py` still owns getting its concrete
`Container` off `request.app.state` and its `JwtVerifier` instance off
that container -- only the token-parsing/verification-to-HTTPException
mapping lives here, so this module has no dependency on any service's
`Container` type.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from .jwt_verifier import JwksCircuitOpenError, JwksFetchError, JwtVerificationError, JwtVerifier

_BEARER_PREFIX = "Bearer "


def get_correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-Id") or str(uuid.uuid4())


async def get_authenticated_user_id(
    request: Request, jwt_verifier: Callable[[], JwtVerifier]
) -> uuid.UUID:
    """`jwt_verifier` is a callable, not the verifier itself: the caller's
    own container lookup must stay lazy, since the original per-service
    implementations never dereferenced the container on the missing/empty
    -token early-exit paths below (some callers legitimately pass no
    container at all on those paths -- see food-recognition-service's
    test_http_dependencies.py for the exact cases this preserves)."""
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

    try:
        principal = await jwt_verifier().verify(token)
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
