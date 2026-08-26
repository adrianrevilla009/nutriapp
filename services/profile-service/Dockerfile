# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT (see docker-compose.yml and
# .github/workflows/profile-service-ci.yml's build-image job), not
# services/profile-service, because this service depends on
# packages/shared-contracts (shared_contracts.auth.jwt_verifier,
# ADR-0022) as a local (non-editable) path dependency declared in
# pyproject.toml's [tool.uv.sources] -- non-editable so `uv sync` produces
# a self-contained install inside .venv/site-packages, since the runtime
# stage below only copies .venv, not the source tree.
FROM python:3.12-slim AS builder
# Mirrors the repo's own relative layout (services/profile-service and
# packages/shared-contracts as siblings under the same root) so
# pyproject.toml's [tool.uv.sources] path ("../../packages/shared-contracts")
# resolves correctly inside the build -- a flatter layout can't satisfy a
# two-levels-up relative path without going above the container's root.
WORKDIR /repo
COPY packages/shared-contracts/ packages/shared-contracts/
COPY services/profile-service/pyproject.toml services/profile-service/uv.lock services/profile-service/
WORKDIR /repo/services/profile-service
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
RUN useradd --uid 1000 --create-home app
WORKDIR /app
COPY --from=builder /repo/services/profile-service/.venv /app/.venv
COPY services/profile-service/domain/ domain/
COPY services/profile-service/application/ application/
COPY services/profile-service/infrastructure/ infrastructure/
COPY services/profile-service/migrations/ migrations/
COPY services/profile-service/alembic.ini ./
USER app
ENV PATH="/app/.venv/bin:$PATH"
# 8000: public API (Kong-routed). 8001: internal-only reveal-metrics API
# (implementation plan Addendum 2) -- never routed through Kong, restricted
# at the NetworkPolicy level to nutrition-calculation-service's pod
# selector only (infra/k8s/charts/profile-service/values.yaml). Both ports
# are served by ONE process (see infrastructure/main.py's `run()`), not two
# containers -- they share one Container (DB pool, KMS client, Redis
# client, RabbitMQ connection).
EXPOSE 8000
EXPOSE 8001
CMD ["python", "-m", "infrastructure.main"]
