# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT (see docker-compose.yml and
# .github/workflows/food-recognition-service-ci.yml's build-image job),
# not services/food-recognition-service, because this service depends on
# packages/shared-contracts as a local (non-editable) path dependency
# declared in pyproject.toml's [tool.uv.sources] -- non-editable so `uv
# sync` produces a self-contained install inside .venv/site-packages,
# since the runtime stage below only copies .venv, not the source tree.
# Mirrors services/nutrition-calculation-service/Dockerfile's shape
# exactly.
FROM python:3.12-slim AS builder
WORKDIR /repo
COPY packages/shared-contracts/ packages/shared-contracts/
COPY services/food-recognition-service/pyproject.toml services/food-recognition-service/uv.lock services/food-recognition-service/
WORKDIR /repo/services/food-recognition-service
# Build shared-contracts into a wheel first, then sync from that wheel
# with --no-build -- pyproject.toml's [tool.uv.sources] points at this
# exact wheel path, not the source directory, specifically so --no-build
# works here instead of needing a NOSONAR exception (python:S8541/S8544;
# verified: pointing at the source directory instead makes --no-build
# fail outright with "has no binary distribution"). `pip install` is
# pinned to an exact version with --only-binary :all:.
RUN pip install --no-cache-dir --only-binary :all: uv==0.12.6 \
    && uv build ../../packages/shared-contracts --wheel -o ../../packages/shared-contracts/dist \
    && uv sync --frozen --no-dev --no-build

FROM python:3.12-slim AS runtime
# libzbar0 is a REQUIRED runtime dependency (not build-only): pyzbar
# (infrastructure/recognition/pyzbar_barcode_decoder.py) loads it via
# ctypes at import time -- it is never bundled into the Python wheel on
# Linux (implementation plan section 1's technology choice). Installed in
# the same apt transaction as the security-hardening cleanup below (one
# update/install/remove/cleanup pass) rather than a second one, to avoid
# re-populating and re-deleting /var/lib/apt/lists twice.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends libzbar0 \
    && apt-get remove -y --purge --allow-remove-essential perl-base \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip \
              /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
    && useradd --uid 1000 --create-home app
WORKDIR /app
COPY --from=builder /repo/services/food-recognition-service/.venv /app/.venv
COPY services/food-recognition-service/domain/ domain/
COPY services/food-recognition-service/application/ application/
COPY services/food-recognition-service/infrastructure/ infrastructure/
COPY services/food-recognition-service/migrations/ migrations/
COPY services/food-recognition-service/alembic.ini ./
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000"]
