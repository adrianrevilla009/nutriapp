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
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Adapt the runtime base and start command per service; keep the two-stage
split and non-root `USER` line non-negotiable.

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
