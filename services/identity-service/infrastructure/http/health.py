"""Liveness/readiness endpoints. Kept dependency-free (no DB/Redis/broker
calls) for liveness; readiness can be extended later to check
dependencies without becoming a synchronous hard dependency chain."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def readiness() -> dict[str, str]:
    return {"status": "ok"}
