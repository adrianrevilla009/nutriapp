"""Asserts the FastAPI app assembled by infrastructure/main.py exposes the
expected routes (composition-level smoke test — Settings.from_env() is
never invoked here since app creation is lazy about it, per main.py)."""
from __future__ import annotations

from infrastructure.main import create_app


def test_create_app__registers_all_expected_routes():
    app = create_app()
    schema = app.openapi()
    paths = set(schema["paths"].keys())
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/auth/login" in paths
    assert "/.well-known/jwks.json" in paths
    assert "/internal/v1/auth/tokens/{reference_id}/reveal" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths
