"""Contract-test app: real Postgres (testcontainers) behind the route,
fake VectorStorePort/EmbeddingPort/ConversationPort/EntitlementCheckPort
swapped in directly on the container. Real signed RS256 JWT verified by a
real JwtVerifier wired against a fake JWKS HTTP client -- mirrors
analytics-service's/recipe-service's/social-service's identical
precedent."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI
from shared_contracts.testing.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from domain.ports.vector_store_port import VectorStoreHit
from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.chat_routes import router as chat_router
from tests.fixtures.fakes import (
    FakeConversationPort,
    FakeEmbeddingPort,
    FakeEntitlementCheckPort,
    FakeVectorStore,
)

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()
_CONTRACT_ROUTERS = (chat_router, health_router)


class _Settings:
    knowledge_base_collection = "nutrition_assistant_knowledge_base"


class _FakeContainer:
    def __init__(self, entitled: bool = True) -> None:
        self.entitlement_check = FakeEntitlementCheckPort(result=entitled)
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)
        self.vector_store = FakeVectorStore(
            hits=[VectorStoreHit(point_id="kb1", score=0.9, payload={"content": "fiber facts"})]
        )
        self.embedding = FakeEmbeddingPort()
        self.conversation = FakeConversationPort(response="Here is your answer.")
        self.settings = _Settings()


def _build_app(container: _FakeContainer, db_engine: AsyncEngine) -> FastAPI:
    app = FastAPI()
    for router in _CONTRACT_ROUTERS:
        app.include_router(router)
    app.state.container = container

    async def override_get_session():
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_container] = lambda: container
    return app


@pytest.fixture
async def app_client(db_engine: AsyncEngine):
    container = _FakeContainer()
    app = _build_app(container, db_engine)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, container


def auth_headers(user_id: uuid.UUID) -> dict:
    token = build_signed_token(_TEST_PRIVATE_KEY, user_id)
    return {"Authorization": f"Bearer {token}"}
