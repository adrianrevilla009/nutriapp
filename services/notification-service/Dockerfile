# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT (see docker-compose.yml and
# .github/workflows/notification-service-ci.yml's build-image job), not
# services/notification-service, because this service depends on
# packages/shared-contracts as a local (non-editable) path dependency
# declared in pyproject.toml's [tool.uv.sources]. Mirrors
# services/food-recognition-service/Dockerfile's shape exactly.
FROM python:3.12-slim AS builder
WORKDIR /repo
COPY packages/shared-contracts/ packages/shared-contracts/
COPY services/notification-service/pyproject.toml services/notification-service/uv.lock services/notification-service/
WORKDIR /repo/services/notification-service
RUN pip install --no-cache-dir --only-binary :all: uv==0.12.6 \
    && uv build ../../packages/shared-contracts --wheel -o ../../packages/shared-contracts/dist \
    && uv sync --frozen --no-dev --no-build

FROM python:3.12-slim AS runtime
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get remove -y --purge --allow-remove-essential perl-base \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip \
              /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
    && useradd --uid 1000 --create-home app
WORKDIR /app
COPY --from=builder /repo/services/notification-service/.venv /app/.venv
COPY services/notification-service/domain/ domain/
COPY services/notification-service/application/ application/
COPY services/notification-service/infrastructure/ infrastructure/
COPY services/notification-service/migrations/ migrations/
COPY services/notification-service/alembic.ini ./
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000"]

