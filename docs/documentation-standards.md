# Documentation Standards

## 1. Per-Service README

Every service under the repository root has its own `README.md` with, at minimum:
- **Purpose**: one paragraph, what bounded context this service owns.
- **How to run locally**: exact commands (assumes `docker-compose up` at the
  repo root already covers most needs; note any service-specific env vars).
- **How to test**: exact commands per test layer (unit/integration/contract/e2e).
- **Owned events**: which domain events this service publishes, with a link to
  their schema in `docs/events-catalog.md`.
- **Consumed events**: which events from other services this service listens to,
  and why.
- **External dependencies**: third-party APIs/services this service integrates
  with, including the resilience pattern applied to each (circuit breaker
  thresholds, timeout, fallback behavior).

## 2. API Documentation

- Every service's public HTTP API is documented via OpenAPI, generated
  automatically by FastAPI from Pydantic models and route definitions — do not
  hand-write OpenAPI specs that can drift from the code.
- Internal (service-to-service) APIs are documented the same way, even though
  they are not exposed to the public internet.

## 3. Event Catalog

`docs/events-catalog.md` is the single registry of every domain event in the
system. Each entry includes: event name, version, producing service, JSON
Schema of the payload, and a one-line description of when it is emitted. Any
new event or breaking schema change must update this file as part of the same
pull request.

## 4. Architecture Decision Records

See `docs/adr/`. Any decision that changes the stack, service boundaries,
messaging backbone, testing strategy, or infrastructure platform (cluster
orchestration, secrets management, API gateway) requires a new ADR
(use `/adr`), following `docs/adr/template.md`.

## 5. Diagrams

High-level architecture diagrams (service map, data flow, sequence diagrams for
key user journeys, deployment topology) live in `ARCHITECTURE.md` at the
repository root, expressed as text-based diagrams (ASCII or Mermaid) so they
stay diffable in git and readable directly in a terminal or on GitHub.

## 6. Inline Code Documentation

- Public functions/classes in the application and domain layers have docstrings
  explaining intent (the "why"), not restating the implementation (the "what"
  should be clear from well-named code).
- Complex domain rules (e.g. a specific core formula) cite their source
  (e.g. a named method or published standard) directly in the docstring or a nearby
  comment.

## 7. Operational Documentation

Beyond code and API documentation, the following operational documents are
kept current as part of the same discipline — not written once and
forgotten:
- `docs/api-catalog.md` — every public/internal HTTP API surface, updated in
  the same PR that adds, changes, or deprecates an endpoint.
- `docs/environments-and-promotion.md`, `docs/observability-slo.md`,
  `docs/incident-response.md`, `docs/backup-and-disaster-recovery.md` —
  reviewed whenever the underlying infrastructure or SLOs change.
- `docs/cost-management.md` — reviewed monthly per its own review cadence.
