# ADR-0001: Hexagonal Architecture (Ports & Adapters) per Service

## Status
Accepted

## Date
2026-08-23

## Context
NutriApp will grow into multiple independently owned services (see ADR-0003).
Each service mixes framework code (FastAPI, SQLAlchemy), third-party integrations
(third-party APIs, ML/vision models, message brokers), and genuine business logic
(core domain calculations, transactional rules, anomaly detection). Without a
clear separation, business logic tends to leak into HTTP handlers and ORM models,
making it hard to test in isolation and expensive to change frameworks later.

## Decision
Every service is structured using Hexagonal Architecture (Ports & Adapters):
- A **domain** layer with zero framework dependencies (pure Python, entities,
  value objects, domain events, domain services).
- An **application** layer orchestrating use cases (command/query handlers) that
  depend only on domain objects and on ports (interfaces) it defines.
- An **infrastructure** layer implementing those ports as adapters (Postgres
  repositories, RabbitMQ publishers, HTTP controllers, external API clients).

Dependencies always point inward: infrastructure depends on application, application
depends on domain, domain depends on nothing external.

## Considered Alternatives
- **Layered (N-tier) architecture** — simpler to start with, but business logic
  tends to bleed into the service/controller layer over time; harder to test the
  domain without spinning up the framework.
- **Transaction Script only (no explicit domain layer)** — fastest to write
  initially, but core domain calculations and event-sourced aggregates need real
  domain modeling to stay correct and testable as complexity grows.

## Consequences
### Positive
- Domain logic (the most valuable and most bug-sensitive part of the system) is
  testable with fast, dependency-free unit tests.
- Swapping infrastructure (e.g. Postgres -> another DB, RabbitMQ -> Kafka) touches
  only the infrastructure layer.
- Enforces a vocabulary (ports) that makes service boundaries and dependencies
  explicit and reviewable.

### Negative / Trade-offs
- More boilerplate than a simple CRUD service, especially for genuinely simple
  domains — mitigated by allowing lighter-weight CRUD-behind-ports for services
  where CQRS/event sourcing does not apply (see ADR-0002).
- Requires discipline; `architecture-agent` and `reviewer-agent` are responsible
  for catching layer violations during review.

### Follow-up actions
- `architecture-agent` enforces this structure on every new service scaffold.
- Add a lint rule / import-boundary check (e.g. `import-linter` for Python) per
  service to fail CI on domain-layer imports of infrastructure packages.

## References
- CLAUDE.md, section 2.1
