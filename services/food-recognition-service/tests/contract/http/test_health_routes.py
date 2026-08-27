async def test_liveness_probe(app_client):
    response = await app_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_probe(app_client):
    response = await app_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
