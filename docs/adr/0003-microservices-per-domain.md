# ADR-0003: Microservices Split per Domain

## Status
Accepted

## Date
2026-08-23

## Context
NutriApp spans clearly distinct business capabilities (identity, reference catalog,
core transactions, derived computation, media recognition, analytics, conversational
AI) with different scaling needs, different failure domains, and different data
ownership. Building this as a single monolith would couple unrelated concerns
(e.g. a spike in vision API load could degrade authentication) and make it harder
to reason about which subagent owns which part of the system.

## Decision
Split the system into one microservice per bounded context, matching the domains
listed in CLAUDE.md section 2.2: `identity-service`, `catalog-service`,
`diary-service`, `nutrition-calculation-service`, `food-recognition-service`, `analytics-service`,
`nutrition-assistant-service`. Each service:
- Owns its own database (no shared schemas).
- Is independently deployable and independently testable.
- Exposes a versioned public API (REST) and/or publishes domain events; it never
  reaches into another service's database directly.
- Maps 1:1 to a dedicated Claude Code subagent, so agent boundaries mirror
  service boundaries.

## Considered Alternatives
- **Modular monolith** — lower operational overhead (one deployable, one DB),
  easier for a solo developer to run locally. Rejected as the primary approach
  because it works against the explicit goal of practicing parallel, isolated
  agent work (git worktrees / subagents per domain) — but see Follow-up actions
  for a pragmatic local-development compromise.
- **Full microservices with Kubernetes from day one** — unnecessary operational
  complexity for a project at this stage; Docker Compose is sufficient until
  real scaling needs appear.

## Consequences
### Positive
- Clean mapping between business domain, codebase boundary, and AI agent
  ownership — exactly the multi-agent workflow this project is designed to
  practice.
- Independent deployability and independent test suites per service.
- Failure isolation: a vision API outage does not take down authentication or
  logging.

### Negative / Trade-offs
- More operational overhead than a monolith: more Dockerfiles, more CI jobs,
  more inter-service contracts to maintain.
- Local development requires orchestrating multiple services (Docker Compose)
  even for small changes.
- Distributed transactions are impossible; the Outbox pattern and eventual
  consistency are required (see CLAUDE.md section 2.4).

### Follow-up actions
- For local development, all services run via a single `docker-compose.yml` at
  the repository root, so a solo developer does not need N terminals.
- Each service still gets its own `Dockerfile` and its own CI pipeline stage.
- `devops-agent` owns keeping `docker-compose.yml` in sync as new services are
  added.

## References
- CLAUDE.md, section 2.2 and section 5
