from __future__ import annotations

from fastapi.testclient import TestClient

from infrastructure.http.health import router


def test_liveness_and_readiness_ok():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}
