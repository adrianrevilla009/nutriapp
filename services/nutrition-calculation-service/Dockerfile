# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT (see docker-compose.yml and
# .github/workflows/nutrition-calculation-service-ci.yml's build-image
# job), not services/nutrition-calculation-service, because this service
# depends on packages/shared-contracts as a local (non-editable) path
# dependency declared in pyproject.toml's [tool.uv.sources] -- non-editable
# so `uv sync` produces a self-contained install inside .venv/site-packages,
# since the runtime stage below only copies .venv, not the source tree.
# Mirrors services/diary-service/Dockerfile's shape exactly.
FROM python:3.12-slim AS builder
WORKDIR /repo
COPY packages/shared-contracts/ packages/shared-contracts/
COPY services/nutrition-calculation-service/pyproject.toml services/nutrition-calculation-service/uv.lock services/nutrition-calculation-service/
WORKDIR /repo/services/nutrition-calculation-service
RUN pip install --no-cache-dir --only-binary :all: uv==0.12.6 && uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
RUN useradd --uid 1000 --create-home app
WORKDIR /app
COPY --from=builder /repo/services/nutrition-calculation-service/.venv /app/.venv
COPY services/nutrition-calculation-service/domain/ domain/
COPY services/nutrition-calculation-service/application/ application/
COPY services/nutrition-calculation-service/infrastructure/ infrastructure/
COPY services/nutrition-calculation-service/migrations/ migrations/
COPY services/nutrition-calculation-service/alembic.ini ./
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000"]
