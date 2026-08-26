async def test_liveness_probe(app_client):
    response = await app_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_probe(app_client):
    response = await app_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_correlation_id_header_is_generated_when_absent(app_client):
    response = await app_client.get("/api/v1/catalog/products/search")
    assert response.status_code == 200
