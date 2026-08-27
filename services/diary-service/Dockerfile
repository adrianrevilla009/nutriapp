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
RUN pip install --no-cache-dir --only-binary :all: uv==0.12.6 && uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
# The runtime image never invokes system python/pip -- it only ever runs
# .venv/bin/python (see PATH below), which uv sync populated fully and
# self-containedly. System pip (and perl-base, an unrelated OS package
# neither apt nor the app needs post-build) are dead weight that Trivy
# still scans: pip vendors its own copies of msgpack and pkg_resources
# (setuptools) at versions with known HIGH-severity CVEs
# (GHSA-6v7p-g79w-8964, CVE-2025-47273), and perl-base carries several
# unfixed/fix-deferred upstream CVEs in this base image tag. Removing the
# actually-unused code is a real fix, not a suppression -- there is
# nothing left in the image to be vulnerable.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get remove -y --purge --allow-remove-essential perl-base \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip \
              /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
    && useradd --uid 1000 --create-home app
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
