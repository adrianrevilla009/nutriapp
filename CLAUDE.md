# NutriApp — AI-native nutrition tracking platform for logging food from a supermarket product catalog or AI-detected photos, understanding macro/micro nutrient intake, and unlocking social, recipe, and reporting features via a Pro subscription

> **This template has been instantiated for NutriApp.** The domain setup
> pass described in `DOMAIN-SETUP.md` is complete: placeholders are
> resolved, the service table below reflects NutriApp's actual bounded
> contexts, and the four previously-pending ADRs (0014, 0015, 0018, 0020)
> are Accepted. `DOMAIN-SETUP.md` is kept for reference on the process used
> and for instantiating any future sibling project from the same template.

## 1. Product Overview

NutriApp lets users register, browse and search a product inventory
scraped from supermarket APIs, log what they eat — including water intake,
fasting windows, and planned meals — against that inventory or against
AI-recognized food photos and barcode scans, see computed macro and
micronutrient breakdowns, track biometric evolution over time with
auto-calculated goals, log exercise and sync wearables, and, on a paid Pro
plan, share/export data, generate reports, connect with other users, and
publish/discover recipes.

This document is the single source of truth for architecture, engineering
standards, and the operating model for AI agents (Claude Code subagents)
working on this codebase. Domain-specific detail lives in `docs/` and
`.claude/skills/`; this file defines the non-negotiable rules every agent
and every human contributor must follow.

## 2. Architectural Style

### 2.1 Hexagonal Architecture (Ports & Adapters) — mandatory per service

Every microservice is structured in three concentric layers:

```
+-----------------------------------------------+
|  Infrastructure (adapters)                     |
|  HTTP controllers, DB repositories,            |
|  message consumers/producers, external APIs    |
|  +-------------------------------------+       |
|  |  Application (use cases)             |       |
|  |  Command/Query handlers, DTOs,       |       |
|  |  orchestration, transaction scripts  |       |
|  |  +-------------------------------+   |       |
|  |  |  Domain (core)                 |   |       |
|  |  |  Entities, Value Objects,      |   |       |
|  |  |  Aggregates, Domain Events,    |   |       |
|  |  |  Domain Services               |   |       |
|  |  |  ZERO framework dependencies   |   |       |
|  |  +-------------------------------+   |       |
|  +-------------------------------------+       |
+-----------------------------------------------+
```

Rules (technology-agnostic; substitute the equivalent for your chosen stack):
- The domain layer must not import your web framework, ORM, or any
  infrastructure library. Dependencies point inward only (Dependency
  Inversion Principle).
- Ports are defined as interfaces/protocols/abstract classes in the domain
  or application layer (e.g. `<Aggregate>RepositoryPort`, `EventPublisherPort`).
- Adapters implement ports and live exclusively in the infrastructure layer
  (e.g. `Postgres<Aggregate>Repository`, `<Broker>EventPublisher`).
- Each service's directory layout:
  ```
  service-name/
    domain/
      entities/
      value_objects/
      events/
      services/
      ports/
    application/
      commands/
      queries/
      handlers/
      dto/
    infrastructure/
      http/
      persistence/
      messaging/
      external/
    tests/
      unit/
      integration/
      contract/
      e2e/
  ```

### 2.2 Microservices — one bounded context per domain

Each domain is an independently deployable service with its own database, its own
deployment pipeline, and its own on-call ownership boundary (even for a solo project,
model it as if a team owned it).

NutriApp's bounded contexts, phased as MVP (Phase 1) vs. Pro/growth
(Phase 2) — see `docs/product-requirements.md` for the full phasing
rationale; all services are specified now regardless of phase, so
`/implementation-plan` can target any of them:

| Service                        | Bounded context                                                                    | Phase |
|---------------------------------|-------------------------------------------------------------------------------------|-------|
| `identity-service`              | Authentication, registration, sessions, authorization, password management          | 1     |
| `profile-service`               | User biometric/health metrics, evolution history, goal-setting engine (calorie/macro targets) | 1 |
| `catalog-service`               | Product inventory scraped from supermarket APIs, search, dietary/allergen filters    | 1     |
| `diary-service`                 | Food logging, water intake, fasting windows, meal planning — the primary transactional domain | 1 |
| `nutrition-calculation-service` | Macro/micro nutrient calculation derived from diary, catalog, and food-recognition data | 1 |
| `food-recognition-service`      | Photo-based AI food detection and barcode product detection                          | 1     |
| `notification-service`          | Transactional email and push delivery                                                | 1     |
| `bff-service`                   | Frontend-facing response aggregation only — orchestration, never business logic (see ADR-0008) | 1 |
| `activity-service`              | Exercise logging and wearable integrations (Apple Health, Google Fit, Fitbit, Garmin) | 2     |
| `recipe-service`                | User recipe definition (with macros/micros), publishing, and cross-user recipe search — Pro-gated | 2 |
| `social-service`                | Connections/following between users, activity feed — Pro-gated                       | 2     |
| `billing-service`               | Pro subscription management, payment processing, feature entitlements                | 2     |
| `analytics-service`             | Trends, reports, evolution graphs, anomaly/threshold detection — reports are Pro-gated | 2 |
| `nutrition-assistant-service`   | RAG assistant grounded in the user's own diary/profile data                          | 2     |

Services communicate:
- **Synchronously** only for query-style, low-latency needs, via internal REST/gRPC,
  always behind a circuit breaker (see 2.6).
- **Asynchronously** (preferred) via a message broker for anything that represents a
  fact that happened (a domain event) — see 2.3.

**Kong** is the single edge entry point (TLS termination, rate limiting, JWT
validation, CORS — configuration, not code). `bff-service` sits behind Kong
and handles response aggregation for specific frontend screens; it contains
orchestration only, never business logic, which stays in the owning domain
service. See ADR-0008 for why these are two separate things rather than one
hand-rolled "gateway."

### 2.3 CQRS + Event Sourcing

- **CQRS + full event sourcing is mandatory for `diary-service` and
  `profile-service`** — both are fundamentally append-only histories
  (diary entries; biometric readings) where evolution/graphs and audit are
  core product value, and event replay is genuinely useful. All other
  services (see 2.2's table) use "event-driven CRUD" — state stored
  conventionally, domain events published as a side effect — per the
  explicit decision recorded in ADR-0002; this is a deliberate choice, not
  a gap.
- **Write model**: normalized, transactional, optimized for consistency. Every state
  change is captured as a **Domain Event** (e.g. `FoodEntryLogged`, `WeightRecorded`,
  named PascalCase past-tense) appended to an **Event Store** (append-only table or a
  dedicated store). The current aggregate state is a fold over its event stream.
- **Read model**: denormalized projections optimized for the exact queries the UI needs,
  built asynchronously by projectors that subscribe to the event stream. Read models are
  disposable — they can always be rebuilt by replaying events.
- **Event schema**: every event has `event_id`, `aggregate_id`, `event_type`, `version`,
  `occurred_at`, `payload`, `metadata` (correlation_id, causation_id, user_id).
  Events are immutable and versioned; breaking changes require a new event version and
  an upcaster, never in-place mutation of historical events.
- Full event sourcing (rebuilding aggregate state purely from events) is required for
  the services you name above as CQRS-mandatory. Other services may adopt "event-driven
  CRUD" (state stored conventionally, events published as a side effect) if that is
  the pragmatic choice — again, document the decision in an ADR.

### 2.4 Messaging Backbone

- Default broker: **RabbitMQ** for command/event routing between services (lighter
  operational footprint for a solo/small-team project than Kafka). Kafka is the
  documented fallback if event replay at scale or stream processing becomes a real
  requirement — see ADR-0004.
- Library: `faststream` (async, type-safe, testable) or `aio-pika` directly for
  lower-level control.
- Naming convention for queues/exchanges: `{service}.{aggregate}.{event_type}`
  (e.g. `diary.food_entry.logged`).
- **Idempotency is mandatory**: every consumer must be safe to receive the same message
  more than once (deduplicate by `event_id`, store processed IDs with a TTL).
- **Outbox pattern** is mandatory for any service that both writes to its own DB and
  publishes an event in the same logical operation, to guarantee at-least-once delivery
  without dual-write inconsistency.
- **Cross-service business transactions** (an operation that must succeed
  or fail as a unit across 2+ services) are never a distributed
  transaction — always a **Saga** (choreography or orchestration), per
  ADR-0019 and `.claude/skills/saga-conventions/SKILL.md`.

### 2.5 Database Strategy

- One database per service (never shared schemas across service boundaries).
- Read/write separation:
  - Write side: PostgreSQL (ACID, strong consistency for the event store / write model).
  - Read side: PostgreSQL read replicas for simple projections; Qdrant for any
    vector-based RAG read model, if the product has an AI assistant; Redis for hot,
    low-latency aggregates.
- Migrations: **Alembic**, one migration history per service. Migrations are additive
  and backward-compatible by default (expand/contract pattern) to support zero-downtime
  deploys. Destructive migrations require an explicit human approval step (see section 7).
- **Multi-tenancy**: NutriApp is single-tenant, B2C (ADR-0018, Accepted) —
  one account per user, no organizations/teams, no tenant-scoped tables.
  See `docs/multi-tenancy.md` for the (short) rationale.

### 2.6 Resilience Patterns

Mandatory for every synchronous inter-service call and every external API call
(third-party data sources, ML/vision APIs, LLM calls):
- **Circuit breaker**: `pybreaker` (or `purgatory` for async). Trip threshold and
  reset timeout must be defined per integration and documented in that service's
  `README.md`.
- **Retry with exponential backoff + jitter**: `tenacity`. Never retry non-idempotent
  operations without a deduplication key.
- **Timeout**: every outbound call has an explicit timeout; no unbounded waits.
- **Bulkhead**: isolate thread/connection pools per external dependency so one slow
  dependency cannot starve the whole service.
- Fallback behavior must be explicit (degrade gracefully, e.g. serve cached data,
  return partial results) and documented per endpoint.

### 2.7 Caching Strategy

- Redis as the shared caching layer.
- Cache-aside pattern by default; write-through only where staleness is unacceptable.
- Explicit TTLs per cache key namespace, documented in
  `.claude/skills/caching-strategy/SKILL.md`.
- Cache invalidation is event-driven where possible (a domain event triggers cache
  invalidation) rather than relying purely on TTL expiry.

### 2.8 Observability & Audit

- Structured logging (JSON) with a correlation ID propagated across service boundaries
  (HTTP header + message metadata).
- Distributed tracing: OpenTelemetry, exported to a local Jaeger instance in development.
- Metrics: Prometheus-compatible `/metrics` endpoint per service.
- **Audit trail is mandatory** for: authentication events, data exports, account
  deletion, and any admin action. Audit records are immutable, append-only, and stored
  separately from operational data. See
  `.claude/skills/observability-audit/SKILL.md`.

### 2.9 Deployment & Infrastructure (summary — full detail in `docs/terraform-and-infrastructure.md` and `docs/containerization-and-orchestration.md`)

- **Monorepo** (ADR-0005): all services, the frontend, `packages/shared-contracts`,
  infra code, and this specification live in one repository. CI runs
  per-service, path-filtered — a change to one service never re-tests every
  other service.
- **Amazon EKS**, no service mesh (ADR-0006): Kubernetes via Helm charts
  built on a shared library chart; resilience patterns from 2.6 handle
  cross-service reliability at the application layer instead of a mesh
  sidecar.
- **Terraform** provisions all AWS infrastructure (VPC, EKS, RDS,
  ElastiCache, messaging, Qdrant, Secrets Manager, DNS/TLS), one state file
  per environment (`dev`/`staging`/`prod`), remote state in S3+DynamoDB.
  **`terraform apply`/`destroy` are never run by an agent** — see section 7.
- **Secrets** (ADR-0007): AWS Secrets Manager, synced into Kubernetes via
  External Secrets Operator, scoped per service via IRSA — no service can
  read another service's secrets.
- **Kong** is the API gateway edge; **`bff-service`** is the aggregation
  layer behind it (ADR-0008, section 2.2).
- **CI/CD**: GitHub Actions, path-filtered per service, gated at every stage
  (lint -> tests -> coverage -> image scan -> deploy-dev -> smoke -> staging
  -> **manual approval** -> prod). See `docs/ci-cd-strategy.md`.

## 3. Testing Strategy (summary — full detail in `docs/testing-strategy.md`)

- **TDD is the default workflow**: red -> green -> refactor. No production code without
  a failing test written first, except for pure scaffolding/boilerplate.
- Testing pyramid target distribution:
  - Unit tests: ~70% of the suite. Fast, no I/O, test the domain layer in isolation.
  - Integration tests: ~20%. Test adapters against real (containerized) dependencies
    via `testcontainers`.
  - Contract tests: cover every inter-service API and every published event schema
    (Pact or schema-based contract tests).
  - End-to-end tests: ~10%. Critical user journeys only — NutriApp's:
    1. Register -> log a food item from catalog search -> see macro/micro totals.
    2. Upload a food photo -> AI detects the item -> logged with computed nutrients.
    3. Upgrade to Pro -> publish a recipe -> another user finds it in recipe search.
- **Coverage targets**: domain layer >= 90% line coverage, application layer >= 85%,
  infrastructure layer >= 70% (infrastructure is thinner and partially covered by
  integration tests instead). Coverage is measured per service, enforced in CI,
  and a merge is blocked below threshold.
- Mutation testing (`mutmut` or `cosmic-ray`) is recommended for the domain layer of
  any service whose correctness is safety- or compliance-sensitive.
- **Load/performance testing is separate from this pyramid** and does not run
  on every PR — see `docs/performance-testing.md` and
  `docs/observability-slo.md` for SLO targets and when load tests gate a
  prod promotion.

## 4. Per-Service Technology Stack

| Concern                | Library / Tool                                              |
|--------------------------|-----------------------------------------------------------|
| Web framework           | FastAPI                                                       |
| Data validation          | Pydantic v2                                                   |
| ORM (write model)        | SQLAlchemy 2.x (async)                                         |
| Migrations               | Alembic                                                       |
| Dependency injection      | `punq` or `dependency-injector`                                 |
| Messaging                | `faststream` (RabbitMQ backend)                                 |
| Circuit breaker           | `pybreaker` / `purgatory` (async)                                |
| Retry                    | `tenacity`                                                    |
| Caching                  | `redis-py` (async client)                                       |
| Vector store             | Qdrant client (only if the product has an AI assistant)          |
| Testing                  | `pytest`, `pytest-asyncio`, `testcontainers`, `factory_boy`      |
| Contract testing         | `pact-python` or JSON Schema-based event contract tests           |
| Coverage                 | `coverage.py` / `pytest-cov`                                     |
| Static analysis          | `ruff`, `mypy` (strict mode)                                      |
| Observability            | `opentelemetry-sdk`, `structlog`, `prometheus-client`              |
| API documentation        | OpenAPI (auto-generated by FastAPI) + `Redocly` for hosting         |
| Load testing             | k6 (or Locust) — see `docs/performance-testing.md`                   |
| Feature flags            | Unleash — see `docs/feature-flags.md`                                  |

Frontend: React + Next.js, TypeScript strict mode, TanStack Query for server state,
Zod for runtime validation matching backend Pydantic schemas. Full spec:
`docs/frontend-architecture.md`.

Infrastructure: Terraform (AWS), Amazon EKS + Helm, Kong (API gateway),
AWS Secrets Manager + External Secrets Operator, GitHub Actions (CI/CD).
Full spec: `docs/terraform-and-infrastructure.md`,
`docs/containerization-and-orchestration.md`, `docs/ci-cd-strategy.md`.

## 5. Domain-to-Agent Mapping

Each domain maps to a dedicated Claude Code subagent (`.claude/agents/`), which owns
that service's hexagonal boundaries, event contracts, and test suite:

- `identity-agent` -> identity-service
- `profile-agent` -> profile-service
- `catalog-agent` -> catalog-service
- `diary-agent` -> diary-service (the primary transactional service)
- `nutrition-calculation-agent` -> nutrition-calculation-service
- `food-recognition-agent` -> food-recognition-service
- `activity-agent` -> activity-service
- `recipe-agent` -> recipe-service
- `social-agent` -> social-service
- `billing-agent` -> billing-service
- `analytics-agent` -> analytics-service
- `nutrition-assistant-agent` -> nutrition-assistant-service
- `notification-agent` -> notification-service (email + push delivery, see ADR-0011)

Cross-cutting agents (domain-agnostic, keep as-is):
- `architecture-agent` — guards hexagonal boundaries, CQRS/event sourcing
  conventions, cross-service saga design
  (`docs/sagas-and-distributed-transactions.md`), the domain glossary/context
  map (`docs/domain-glossary-and-context-map.md`), and reviews any change
  that crosses service boundaries.
- `qa-agent` — owns test strategy enforcement, coverage gates, static code
  quality gates (`docs/code-quality.md`), and TDD discipline.
- `devops-agent` — CI/CD pipelines, Dockerfiles, docker-compose, migrations,
  deployment strategy (`ADR-0017`).
- `infra-agent` — Terraform (AWS), Kubernetes/Helm, secrets infrastructure,
  backup/DR configuration (`docs/disaster-recovery-runbook.md`),
  multi-region posture (`docs/multi-region-strategy.md`), cost posture.
  See `.claude/agents/infra-agent.md`.
- `security-agent` — authN/authZ review (`docs/authorization-model.md`),
  secrets handling, audit trail correctness, and — given NutriApp stores
  GDPR Article 9 special-category biometric/health data in
  `profile-service` — sensitive personal data protection is a standing,
  non-optional review concern, not an edge case. Also owns the vendor risk
  register (`docs/vendor-risk-register.md`) and compliance control mapping
  (`docs/compliance-mapping.md`, GDPR baseline per ADR-0020).
- `reviewer-agent` — final read-only review gate before any change is considered done.

## 6. Human-in-the-Loop Workflow (mandatory)

Every non-trivial change follows this pipeline, each stage a separate, explicit gate:

1. **Spec** — the requirement is written down (what, why, acceptance criteria).
2. **Implementation Plan** (`/implementation-plan`) — an agent produces a concrete plan
   (files to touch, ports/adapters affected, events introduced or consumed, test plan
   reference). No code is written yet.
3. **Human approval of the plan.**
4. **Test Plan** (`/test-plan`) — test cases are defined before implementation (TDD).
5. **Human approval of the test plan** (lightweight, can be combined with step 3 for
   small changes).
6. **Implementation Execution** (`/implementation-execution`) — code is written to make
   the planned tests pass.
7. **Test Execution** (`/test-execution`) — full test suite run, coverage checked.
8. **Implementation Review** (`/implementation-review`) — `reviewer-agent` and/or
   `architecture-agent` review the diff against CLAUDE.md and the relevant skills.
9. **Test Review** (`/test-review`) — verify tests actually assert behavior (not
   tautological), and coverage/mutation thresholds are met.
10. **Human final approval.**
11. **Commit** (`/create-commit`) — conventional commit, scoped to one logical change.
12. **Pull Request** (`/create-pr`) — PR description auto-generated from the plan +
    review findings, opened for human merge approval.

No agent skips a gate. No agent merges or pushes without explicit human confirmation
(enforced by `.claude/hooks/pre-bash-guard.sh` and `.claude/hooks/subagent-stop-gate.sh`).

## 7. Non-negotiable Guardrails

Never execute without explicit human confirmation:
- `git push`, force-push, or branch deletion.
- Destructive database migrations (`DROP TABLE`, `DROP DATABASE`, `TRUNCATE`,
  non-additive column changes).
- `terraform apply` or `terraform destroy`, in any environment, under any
  flag (including `-auto-approve`) — only `terraform plan` is allowed
  unattended. Enforced by `.claude/hooks/pre-terraform-guard.sh`.
- `kubectl delete`, `helm uninstall`/`delete`, or any other command that
  removes a running resource from a real cluster.
- Bulk/production-scale scraping or bulk ingestion runs against third-party sources.
- Deletion of user data or audit records, including the crypto-shredding
  step of the erasure flow in `docs/data-protection-and-privacy.md`.
- Any change to `.claude/settings.json` hooks or permission configuration.

## 8. Legal & Ethical Constraints

- **Supermarket product data (`catalog-service`)**: scraping respects each
  source's `robots.txt`, published rate limits, and terms of service —
  see `.claude/skills/external-data-ethics/SKILL.md`. Only catalog/reference
  data (product names, nutrition facts, barcodes, pricing) is ingested;
  no personal data of third parties is ever scraped.
- **Biometric/health data (`profile-service`)**: weight, body metrics, and
  any dietary/medical condition fields are GDPR Article 9 "special category"
  data. They require explicit, specific consent (not bundled into general
  ToS acceptance) and a documented lawful basis before collection;
  collection is minimized to what each feature (goal-setting, evolution
  graphs) actually needs. Users retain the right to erasure, implemented
  via crypto-shredding per `docs/data-protection-and-privacy.md`. No
  formal certification (SOC 2, HIPAA) is pursued at this stage — see
  ADR-0020.
- **AI assistant boundary (`nutrition-assistant-service`)**: it surfaces
  the user's own logged data and general nutrition information only. It
  must never claim to provide medical nutrition therapy, diagnose a
  condition, or otherwise act as a licensed dietitian or physician; every
  response touching a health-adjacent topic (deficiency risk, disordered-
  eating-adjacent patterns) carries a visible disclaimer to consult a
  qualified professional. This boundary is enforced in the system prompt
  and evaluated per `.claude/skills/rag-conventions/SKILL.md`.
- **AI food/photo recognition (`food-recognition-service`)**: confidence
  scores are surfaced to the user rather than silently auto-accepted for
  low-confidence detections, per `.claude/skills/media-recognition-conventions/SKILL.md`.
- **User-published content (`recipe-service`, `social-service`)**: users
  publishing recipes or connecting with other users are made aware their
  content/profile becomes visible to other users; this is a distinct
  consent surface from the general product ToS.

## 9. Architecture Decision Records (ADRs)

Every significant architectural choice is documented as an ADR in `docs/adr/`,
following the template in `docs/adr/template.md`. Current ADRs (rename titles
to match your domain decisions where the ADR references example services):
- ADR-0001: Hexagonal architecture per service
- ADR-0002: CQRS and event sourcing scope
- ADR-0003: Microservices split per domain
- ADR-0004: Messaging backbone (RabbitMQ, with Kafka as documented fallback)
- ADR-0005: Monorepo with per-service CI pipelines
- ADR-0006: Container orchestration on Amazon EKS, no service mesh
- ADR-0007: AWS Secrets Manager + External Secrets Operator for secrets
- ADR-0008: Kong (self-hosted on EKS) as the API Gateway, with a separate `bff-service`
- ADR-0009: SAST (Semgrep), SBOM generation, and proactive dependency updates
- ADR-0010: CloudFront (CDN) and AWS WAF at the edge
- ADR-0011: `notification-service`, transactional email (SES), and push (SNS)
- ADR-0012: Catalog search strategy (supermarket product inventory)
- ADR-0013: Product analytics (self-hosted PostHog)
- ADR-0014: Mobile app strategy — responsive web first, native later (Accepted)
- ADR-0015: Billing and monetization — freemium with Pro subscription (Accepted)
- ADR-0016: Chaos engineering in `staging` (AWS FIS)
- ADR-0017: Deployment strategy (rolling -> canary/blue-green activation triggers)
- ADR-0018: Multi-tenancy strategy — single-tenant, B2C (Accepted)
- ADR-0019: Saga pattern for cross-service business transactions
- ADR-0020: Target compliance framework — GDPR baseline (Accepted)
- ADR-0021: Scale north star and revisit triggers

Propose new ADRs via `/adr` whenever a decision changes the stack, the messaging
backbone, the service boundaries, or the testing strategy.

## 10. Documentation Standards

See `docs/documentation-standards.md` and
`.claude/skills/documentation-standards/SKILL.md`. Summary:
- Every service has its own `README.md` (purpose, how to run, how to test, owned
  events, dependencies).
- Every public API is documented via OpenAPI, kept in sync automatically (FastAPI),
  and listed in `docs/api-catalog.md` alongside its version/deprecation status.
- Every published/consumed event is documented in `docs/events-catalog.md`.
- Architecture-level diagrams live in `ARCHITECTURE.md`.

## 11. MCP Integrations

See `docs/mcp-servers.md` for the full MCP catalog (GitHub, Postgres
inspection, Slack, browser/e2e, Qdrant, observability, error tracking,
infrastructure, issue tracking — including free/self-hosted alternatives
to paid options) and how to wire them into `.claude/settings.json`. All
entries are currently **disabled**; the project runs locally and each
server is activated only when its documented activation condition is
met.

## 12. Operational Readiness (summary — full detail in the linked docs)

Beyond code and architecture, the following are mandatory parts of "done"
for anything reaching `staging`/`prod`:
- **Environments & promotion**: `docs/environments-and-promotion.md` —
  `dev` -> `staging` -> **manual approval** -> `prod`, never a direct-to-prod path.
- **Observability & SLOs**: `docs/observability-slo.md` — SLIs/SLOs per
  service, error budgets, burn-rate alerting.
- **Incident response**: `docs/incident-response.md` — severity levels,
  blameless postmortems; guardrails from section 7 remain active even during
  an incident.
- **Backup & DR**: `docs/backup-and-disaster-recovery.md` — RPO/RTO targets,
  quarterly restore drills.
- **Performance**: `docs/performance-testing.md` — load/stress/soak/spike
  tests against `staging`, gating prod promotion for hot-path changes.
- **Cost**: `docs/cost-management.md` — non-prod scale-to-zero, tagging,
  metered-external-API cost controls.
- **Data protection**: `docs/data-protection-and-privacy.md` — consent,
  minimization, third-party AI data handling, right-to-erasure via
  crypto-shredding.
- **Feature flags**: `docs/feature-flags.md` — deploy/release decoupling,
  kill switches for external-dependency risk.
- **Frontend**: `docs/frontend-architecture.md` — structure, state
  management, accessibility, i18n.
- **Monorepo tooling**: `docs/monorepo-tooling.md` — workspace boundaries,
  shared contracts package.
- **AI agent governance**: `docs/ai-agent-governance.md` — decision
  authority boundaries for both development-time agents and any
  product-time AI features.
- **Project status tracking**: `docs/project-status-tracking.md` — how
  actual implementation state (as opposed to specification) is recorded
  and kept current, surfaced via `/project-status`.
- **Supply chain & static security**: `docs/supply-chain-security.md` —
  SAST, SBOM, and proactive dependency updates, beyond the secret/CVE
  scanning already in `docs/ci-cd-strategy.md`.
- **Code quality**: `docs/code-quality.md` — static quality gates
  (complexity, duplication, maintainability) complementing test coverage.
- **Edge (CDN & WAF)**: `docs/edge-and-cdn.md` — CloudFront caching and AWS
  WAF rollout, in front of the API gateway from ADR-0008.
- **Notifications**: `docs/notifications.md` — transactional email and push
  delivery, owned by `notification-service` (ADR-0011).
- **Chaos & resilience testing**: `docs/chaos-engineering.md` — verifying
  the resilience patterns in section 2.6 hold under real, not mocked,
  failure.
- **Authorization**: `docs/authorization-model.md` — RBAC/ABAC model,
  token scoping, and enforcement boundaries.
- **Multi-tenancy**: `docs/multi-tenancy.md` — data isolation and tenant
  lifecycle, once ADR-0018 selects an option.
- **Distributed transactions**: `docs/sagas-and-distributed-transactions.md`
  — the catalog of every cross-service business transaction and its
  compensating actions (ADR-0019).
- **Compliance**: `docs/compliance-mapping.md` — control-to-evidence
  mapping for whichever framework(s) ADR-0020 selects.
- **Domain glossary & context map**: `docs/domain-glossary-and-context-map.md`
  — shared vocabulary and bounded-context relationships (DDD).
- **Data platform**: `docs/data-platform-and-analytics.md` — the
  distinction between domain analytics, product analytics, and any
  future data warehouse/BI layer.
- **External contracts**: `docs/sla-and-contracts.md` — what (if
  anything) is contractually promised to customers, kept distinct from
  internal SLOs.
- **Vendor risk**: `docs/vendor-risk-register.md` — every third-party
  processor, its DPA status, and compliance relevance.
- **Disaster recovery runbook**: `docs/disaster-recovery-runbook.md` —
  the actual restore procedure and quarterly drill cadence, beyond the
  RPO/RTO targets in `docs/backup-and-disaster-recovery.md`.
- **Multi-region**: `docs/multi-region-strategy.md` — current
  single-region scope and the triggers that would change it.
- **Onboarding**: `docs/onboarding.md` — the practical first-hour runbook
  for a new human contributor or a fresh agent session.

## 13. AI-Native Domain Conventions (delete this section if the product has no AI-native features)

Beyond the general architecture in sections 2–4, any AI-native parts of
the product (an assistant grounded in the user's own data, media
recognition) follow dedicated conventions:
- **RAG pipeline**: `.claude/skills/rag-conventions/SKILL.md` — retrieval
  scope, chunking, grounding, hallucination prevention, any professional-
  advice boundary, and evaluation.
- **Media/vision models**: `.claude/skills/media-recognition-conventions/SKILL.md` —
  confidence handling, model lifecycle, and privacy.
- **Prompts**: `.claude/skills/prompt-engineering-standards/SKILL.md` —
  prompts are versioned, reviewed, and evaluated like code.
- **Model/cost selection**: `.claude/skills/llm-cost-and-model-selection/SKILL.md`
  — which model tier to use, for both Claude Code subagents and
  in-product LLM calls.

Cross-cutting product-quality conventions that apply across all services:
- **Internationalization**: `.claude/skills/i18n-conventions/SKILL.md`.
- **Accessibility**: `.claude/skills/accessibility-standards/SKILL.md`.
- **Domain calculations**: `.claude/skills/domain-calculation-conventions/SKILL.md`
  — how to document and test any core business-rule calculations specific
  to your domain (pricing, scoring, eligibility, etc.).

## 14. Current State

**Specification phase only.** No application code and no infrastructure
code exist yet — not a single `.tf`, Helm chart, CI workflow, or service
file. What exists is the complete specification that will guide their
creation: this document, the ADRs in `docs/adr/`, the full operational
specification (CI/CD, Terraform structure, Kubernetes/Helm structure,
secrets, API gateway, backups, data protection, cost) in `docs/`, and the
Claude Code agent/skill/command definitions in `.claude/`.

Every piece of that future implementation — application code and
infrastructure code alike — is created later, incrementally, by following
the human-in-the-loop pipeline in section 6: an agent proposes an
implementation plan referencing the relevant spec doc, a human approves it,
then and only then is any file actually written. This applies equally to
`identity-service`'s application code and to its Terraform/Helm/CI
scaffolding — infrastructure changes are not exempt from the plan-approve-
implement cycle.

Next step: fill in `DOMAIN-SETUP.md`, then propose an implementation plan
for `identity-service` end-to-end (domain -> application -> infrastructure
-> tests), including its Terraform/Helm/CI wiring, as the reference
implementation other services will mirror.
