---
description: Dockerfile and Kubernetes/Helm conventions for NutriApp services. Use whenever creating or modifying a Dockerfile, Helm chart, or Kubernetes manifest.
---

# Containerization Conventions — NutriApp

Full policy: `docs/containerization-and-orchestration.md`. ADR-0006 covers
why EKS with no service mesh.

## Dockerfile Template (Python service)
```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
RUN useradd --uid 1000 --create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# Always invoke via `python -m uvicorn`, never the bare `uvicorn` console
# script -- see note below.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Adapt the runtime base and start command per service; keep the two-stage
split and non-root `USER` line non-negotiable.

**Always use `CMD ["python", "-m", "uvicorn", ...]`, never the bare
`CMD ["uvicorn", ...]` form.** `uv sync` hardcodes an absolute shebang into
`.venv/bin/uvicorn` pointing at the *builder* stage's venv path. If the
runtime stage's `WORKDIR` differs from the builder stage's `WORKDIR` --
which happens for any service that depends on `packages/shared-contracts`,
since its builder stage needs a `/repo`-rooted `WORKDIR` (e.g.
`/repo/services/<name>`) for `pyproject.toml`'s `[tool.uv.sources]` relative
path to resolve, while the runtime stage uses `/app` — that shebang points
at a path that doesn't exist in the runtime stage, and the container
crashes on start with `exec: no such file or directory`. `python -m
uvicorn` resolves the interpreter via `PATH` (the venv's real `python` ELF
binary, set by `ENV PATH="/app/.venv/bin:$PATH"` above) instead of the
shebang'd script, sidestepping the mismatch entirely — with no behavioral
difference. This bug bit 11 services (fixed in PR #36 and the
notification/activity/billing/recipe/social/nutrition-assistant follow-up)
before this template was corrected; don't regress it in a new service's
Dockerfile.

## Rules
- No secrets as `ARG`/`ENV` baked at build time — only injected at runtime via
  Kubernetes Secret/ConfigMap.
- Tag images with the git SHA, never `latest`.
- Every Helm chart's Deployment template MUST include: `resources.requests`
  and `resources.limits`, `livenessProbe`, `readinessProbe`, and a
  `ServiceAccount` with the correct IRSA annotation. A chart missing any of
  these is not ready for review.
- `NetworkPolicy` default-deny per namespace; each service's chart adds only
  the explicit allow rules it needs.
- No service mesh sidecars — resilience is handled at the application layer
  (`.claude/skills/resilience-patterns/SKILL.md`), per ADR-0006.

## Local Dev
`docker-compose.yml` at repo root must stay in parity with each chart's
`values-dev.yaml` config keys — check both when adding a new environment
variable.
