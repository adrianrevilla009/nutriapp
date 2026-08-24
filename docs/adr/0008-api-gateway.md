# ADR-0008: Kong (self-hosted on EKS) as the API Gateway

## Status
Accepted

## Date
2026-08-23

## Context
ARCHITECTURE.md already describes a BFF/API Gateway as "the single entry
point for the frontend... only routing, auth token validation, and request
aggregation." That description conflates two distinct concerns that need
separate treatment:
1. **Edge concerns** that apply uniformly to every request regardless of
   business domain: TLS termination, rate limiting per client, request/response
   logging, auth token validation, CORS.
2. **Aggregation concerns** that are domain-aware: composing a response from
   multiple services for a single frontend screen (e.g. the dashboard needs
   data from `nutrition-calculation-service` and `analytics-service` in one call).

Mixing both in a single hand-rolled FastAPI "gateway" service risks it
accumulating business logic over time, violating CLAUDE.md's explicit rule
that the gateway "does not contain business logic."

## Decision
Split the two concerns:
- **API Gateway (edge)**: Kong, self-hosted on EKS via the official Helm
  chart, sitting behind the ALB Ingress. Handles TLS termination (cert-manager
  + ACM), rate limiting per API key/client, JWT validation (verifying the
  asymmetric signature from `identity-service`, not calling it synchronously),
  request logging/tracing header injection, and CORS.
- **BFF (aggregation)**: a thin, explicitly-named `bff-service` (its own
  hexagonal service, own tests) that composes responses for specific frontend
  screens by calling downstream services. It contains orchestration, never
  business logic — business rules stay in the owning domain service.

## Considered Alternatives
- **AWS API Gateway (managed)** — fully managed, no pods to run, but weaker
  local-development parity (`docker-compose` can't easily emulate it) and
  less flexible plugin ecosystem for the specific rate-limiting/auth patterns
  needed. Rejected in favor of self-hosted Kong for dev/prod parity; revisit
  if operating Kong becomes a maintenance burden.
- **Single hand-rolled FastAPI gateway doing both jobs** — what
  ARCHITECTURE.md originally implied. Rejected because it blurs the "no
  business logic in the gateway" rule and duplicates what a mature gateway
  already solves (rate limiting, JWT validation plugins).
- **No gateway, frontend calls services directly** — rejected; violates the
  single-entry-point requirement and pushes CORS/auth complexity to the
  frontend.

## Consequences
### Positive
- Rate limiting, auth validation, and TLS are configuration, not code —
  fewer bugs, faster to change.
- `bff-service` stays small and testable, with a clear single responsibility
  (aggregation), reviewable by `architecture-agent` like any other service.
- Local dev parity: Kong runs in `docker-compose` too.

### Negative / Trade-offs
- One more moving part to operate (Kong's own database or DB-less
  declarative config — DB-less chosen to avoid yet another stateful
  dependency).
- Two hops for aggregated requests (Kong -> bff-service -> domain services)
  adds latency; acceptable given synchronous calls are already the
  lower-preference option per CLAUDE.md 2.2.

### Follow-up actions
- Add `bff-service` to the service table in CLAUDE.md section 2.2.
- Write Kong declarative config (`infra/k8s/kong/kong.yaml`) with rate-limit
  and JWT-validation plugins.
- Document per-endpoint rate limits in `docs/api-standards.md`.

## References
- `docs/api-standards.md`
- ARCHITECTURE.md section 1 (Service Map)
