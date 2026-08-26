# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT (see docker-compose.yml and
# .github/workflows/diary-service-ci.yml's build-image job), not
# services/diary-service, because this service depends on
# packages/shared-contracts (shared_contracts.auth.jwt_verifier,
# ADR-0022) as a local (non-editable) path dependency declared in
# pyproject.toml's [tool.uv.sources] -- non-editable so `uv sync` produces
# a self-contained install inside .venv/site-packages, since the runtime
# stage below only copies .venv, not the source tree.
FROM python:3.12-slim AS builder
# Mirrors the repo's own relative layout (services/diary-service and
# packages/shared-contracts as siblings under the same root) so
# pyproject.toml's [tool.uv.sources] path ("../../packages/shared-contracts")
# resolves correctly inside the build -- a flatter layout can't satisfy a
# two-levels-up relative path without going above the container's root.
WORKDIR /repo
COPY packages/shared-contracts/ packages/shared-contracts/
COPY services/diary-service/pyproject.toml services/diary-service/uv.lock services/diary-service/
WORKDIR /repo/services/diary-service
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
RUN useradd --uid 1000 --create-home app
WORKDIR /app
COPY --from=builder /repo/services/diary-service/.venv /app/.venv
COPY services/diary-service/domain/ domain/
COPY services/diary-service/application/ application/
COPY services/diary-service/infrastructure/ infrastructure/
COPY services/diary-service/migrations/ migrations/
COPY services/diary-service/alembic.ini ./
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000"]
