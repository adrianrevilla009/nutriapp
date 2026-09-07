from __future__ import annotations

import httpx
from fastapi import FastAPI

from infrastructure.http.health import router as health_router


async def test_liveness_and_readiness_return_ok() -> None:
    app = FastAPI()
    app.include_router(health_router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        live = await client.get("/health/live")
        ready = await client.get("/health/ready")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
