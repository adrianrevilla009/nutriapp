# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT (see docker-compose.yml and
# .github/workflows/nutrition-assistant-service-ci.yml's build-image job),
# not services/nutrition-assistant-service, because this service depends
# on packages/shared-contracts as a local (non-editable) path dependency
# declared in pyproject.toml's [tool.uv.sources]. Mirrors
# services/analytics-service/Dockerfile's shape exactly.
#
# NOVEL vs. every prior service's Dockerfile: LocalEmbeddingAdapter
# (fastembed/ONNX Runtime) downloads sentence-transformers/all-MiniLM-L6-v2
# model weights from Hugging Face Hub on first use if not already cached
# in the image -- this Dockerfile does NOT pre-bake the model weights into
# the image this pass (a real, flagged gap: first request after a fresh
# pod start pays a one-time download+load cost, and prod pods need
# egress to huggingface.co). Pre-baking the model into the image (a
# `RUN python -c "from fastembed import TextEmbedding; TextEmbedding(...)"`
# layer) is a reasonable follow-up, not built here.
FROM python:3.12-slim AS builder
WORKDIR /repo
COPY packages/shared-contracts/ packages/shared-contracts/
COPY services/nutrition-assistant-service/pyproject.toml services/nutrition-assistant-service/uv.lock services/nutrition-assistant-service/
WORKDIR /repo/services/nutrition-assistant-service
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
COPY --from=builder /repo/services/nutrition-assistant-service/.venv /app/.venv
COPY services/nutrition-assistant-service/domain/ domain/
COPY services/nutrition-assistant-service/application/ application/
COPY services/nutrition-assistant-service/infrastructure/ infrastructure/
COPY services/nutrition-assistant-service/migrations/ migrations/
COPY services/nutrition-assistant-service/knowledge_base/ knowledge_base/
COPY services/nutrition-assistant-service/alembic.ini ./
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# Invoked via `python -m uvicorn`, not the `.venv/bin/uvicorn` console-script
# directly: that script's shebang is hardcoded at `uv sync` time to the
# BUILDER stage's absolute venv path (/repo/services/nutrition-assistant-service/.venv/bin/python),
# which does not exist in this runtime stage (/app/.venv) -- running it
# directly fails with "exec ...: no such file or directory". `python -m`
# resolves the interpreter via PATH (the venv's actual python binary, not a
# shebang'd script), sidestepping the mismatch entirely.
CMD ["python", "-m", "uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000"]
