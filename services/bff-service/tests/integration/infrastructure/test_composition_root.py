"""Proves Settings.from_env() and the real Container wiring work
end-to-end -- exercising Container.__init__()/startup()/shutdown()
itself so a wiring typo doesn't go undetected. No testcontainers needed
here (unlike every other service): this service has no database and no
message broker (implementation plan section 2)."""

from __future__ import annotations

from infrastructure.composition_root import Container, Settings


def test_settings_from_env_reads_expected_variables(monkeypatch):
    monkeypatch.setenv("BFF_SERVICE_DIARY_SERVICE_BASE_URL", "http://diary-service.test:8000")
    monkeypatch.setenv(
        "BFF_SERVICE_NUTRITION_CALCULATION_SERVICE_BASE_URL",
        "http://nutrition-calculation-service.test:8000",
    )

    settings = Settings.from_env()

    assert settings.diary_service_base_url == "http://diary-service.test:8000"
    assert (
        settings.nutrition_calculation_service_base_url
        == "http://nutrition-calculation-service.test:8000"
    )
    assert settings.identity_issuer == "identity-service"


def test_settings_from_env_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("BFF_SERVICE_DIARY_SERVICE_BASE_URL", raising=False)
    monkeypatch.delenv("BFF_SERVICE_NUTRITION_CALCULATION_SERVICE_BASE_URL", raising=False)
    monkeypatch.delenv("BFF_SERVICE_IDENTITY_JWKS_URL", raising=False)

    settings = Settings.from_env()

    assert settings.diary_service_base_url == "http://diary-service:8000"
    assert (
        settings.nutrition_calculation_service_base_url
        == "http://nutrition-calculation-service:8000"
    )
    assert settings.identity_jwks_url == "http://identity-service:8000/.well-known/jwks.json"


async def test_container_startup_and_shutdown_wires_both_clients():
    settings = Settings(
        identity_jwks_url="http://identity-service.test/.well-known/jwks.json",
        identity_issuer="identity-service",
        diary_service_base_url="http://diary-service.test:8000",
        nutrition_calculation_service_base_url="http://nutrition-calculation-service.test:8000",
    )
    container = Container(settings)

    assert container.diary_summary_client is not None
    assert container.nutrition_calculation_client is not None
    assert container.jwt_verifier is not None

    await container.startup()
    await container.shutdown()
