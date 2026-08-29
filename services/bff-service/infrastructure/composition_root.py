"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). This service has
NO database and NO messaging (implementation plan section 2): `Container`
holds only the JWT verifier (for the local/dev 401 path, section 9.2) and
the two downstream HTTP clients, each with its own bulkhead + circuit
breaker(s).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from shared_contracts.auth.jwt_verifier import JwtVerifier

from infrastructure.external.diary_service_client import DiaryServiceClient
from infrastructure.external.nutrition_calculation_service_client import (
    NutritionCalculationServiceClient,
)

DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_DIARY_SERVICE_BASE_URL = "http://diary-service:8000"
DEFAULT_NUTRITION_CALCULATION_SERVICE_BASE_URL = "http://nutrition-calculation-service:8000"


@dataclass(frozen=True, slots=True)
class Settings:
    identity_jwks_url: str
    identity_issuer: str
    diary_service_base_url: str
    nutrition_calculation_service_base_url: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            identity_jwks_url=os.environ.get(
                "BFF_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get("BFF_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER),
            diary_service_base_url=os.environ.get(
                "BFF_SERVICE_DIARY_SERVICE_BASE_URL", DEFAULT_DIARY_SERVICE_BASE_URL
            ),
            nutrition_calculation_service_base_url=os.environ.get(
                "BFF_SERVICE_NUTRITION_CALCULATION_SERVICE_BASE_URL",
                DEFAULT_NUTRITION_CALCULATION_SERVICE_BASE_URL,
            ),
        )


class Container:
    """Holds long-lived infrastructure clients. No DB engine, no
    RabbitMQ connection, no background task -- this service is pure
    stateless request/response aggregation (implementation plan
    section 2)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        # Own, isolated connection pool + dedicated circuit breaker(s) per
        # downstream service (resilience-patterns SKILL.md) -- never
        # shared between the two clients.
        self.diary_summary_client = DiaryServiceClient(base_url=settings.diary_service_base_url)
        self.nutrition_calculation_client = NutritionCalculationServiceClient(
            base_url=settings.nutrition_calculation_service_base_url
        )

    async def startup(self) -> None:
        # Nothing to start -- no DB engine, no broker connection, no
        # background worker.
        return None

    async def shutdown(self) -> None:
        await self.diary_summary_client.aclose()
        await self.nutrition_calculation_client.aclose()
