# Containerization & Orchestration

Full specification behind CLAUDE.md's infra summary. See ADR-0006 (EKS, no
mesh) for the platform decision.

## 1. Container Images

- **Multi-stage Dockerfiles**, one per service, following a shared template
  (`.claude/skills/containerization/SKILL.md` has the canonical example):
  a `builder` stage installs dependencies and compiles anything needed, a
  `runtime` stage copies only the artifacts needed to run, on a minimal base
  image (`python:3.12-slim` for backend services, `node:22-alpine` for the
  frontend build stage served via a static/edge runtime).
- **Non-root user** in every runtime image (`USER app`, UID/GID fixed and
  documented, never `root`).
- **No secrets baked into images**, ever — verified by the secret-scan CI
  stage and by `security-agent` review.
- Images are tagged with the git SHA, never `latest`, so a Kubernetes
  deployment is always traceable to an exact commit.
- `.dockerignore` per service excludes tests, `.git`, local `.env` files, and
  anything not needed at runtime, keeping images small.

## 2. Local Development: docker-compose

`docker-compose.yml` at the repo root brings up the full local stack:
Postgres (one instance, one database per service via init scripts), Redis,
RabbitMQ (with the management UI enabled), Qdrant, Jaeger (tracing UI), and
every service in the monorepo, each with hot-reload mounted from source.

This is the reference environment E2E tests run against locally and in CI's
E2E stage (`docs/testing-strategy.md` section 2.4).

## 3. Kubernetes (EKS)

### 3.1 Structure
- One Helm chart per service under `infra/k8s/charts/<service-name>/`,
  built on a shared library chart (`infra/k8s/charts/_lib/`) providing common
  templates: Deployment, Service, HPA, PodDisruptionBudget, NetworkPolicy,
  ServiceAccount (with IRSA annotation), and standard liveness/readiness
  probes hitting each service's `/health` and `/ready` endpoints.
- Values files per environment: `values-dev.yaml`, `values-staging.yaml`,
  `values-prod.yaml` — differ only in replica counts, resource limits, and
  environment-specific config, never in the template logic itself.

### 3.2 Mandatory per-service manifests
- **Resource requests and limits** on every container — no service deploys
  without them (enforced by a Helm chart schema/lint, not just convention).
- **Liveness and readiness probes** — a service that is up but not ready
  (e.g. still connecting to its database) must not receive traffic.
- **HorizontalPodAutoscaler** — scales on CPU and, where relevant (e.g.
  `food-recognition-service` processing photos), a custom metric via the Prometheus
  adapter (queue depth, request latency).
- **PodDisruptionBudget** — guarantees a minimum number of replicas survive
  voluntary disruptions (node drains, cluster upgrades).
- **NetworkPolicy** — default-deny ingress per namespace; each service
  explicitly allows only the traffic it needs (from the Kong gateway, from
  specific other services it's a legitimate consumer of, from Prometheus for
  scraping metrics).

### 3.3 Namespaces
- One namespace per environment (`nutriapp-dev`, `nutriapp-staging`,
  `nutriapp-prod`), not per service — service-level isolation is handled by
  NetworkPolicy and IRSA, not namespace boundaries, to keep RBAC manageable
  for a solo operator.

### 3.4 Ingress
- AWS Load Balancer Controller provisions an ALB from Ingress resources.
- TLS via ACM certificates, referenced in the Ingress annotation.
- All external traffic terminates at Kong (ADR-0008) before reaching any
  service.

## 4. No Service Mesh (see ADR-0006)

Explicitly not using Istio/Linkerd at this stage. Cross-service resilience
(circuit breakers, retries, timeouts) is handled at the application layer per
CLAUDE.md 2.6. Traffic segmentation is handled by NetworkPolicy. Revisit if
team size or compliance requirements change.

## 5. Rollout Strategy

- Default: **rolling update** (Kubernetes native), `maxSurge: 1`,
  `maxUnavailable: 0` for stateless services, ensuring zero-downtime deploys.
- Services with expensive cold starts (`nutrition-assistant-service`, `food-recognition-service`
  loading model weights) use a `readinessProbe` with a generous
  `initialDelaySeconds` and `startupProbe` to avoid being killed during
  legitimate warm-up.
- Canary/blue-green is not implemented for MVP; tracked as a follow-up once
  `feature-flags.md`'s tooling is in place and traffic volume justifies it.

## 6. Local-to-Prod Parity Checklist

Before any Helm chart is considered done, verify:
- The same container image builds and runs identically via `docker-compose`
  and via the Helm chart (only config/secrets differ, injected via env vars).
- `.env.example` and the chart's `values-dev.yaml` list the same configuration
  keys, so nothing is prod-only-discovered.
