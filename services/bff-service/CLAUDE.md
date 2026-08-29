# bff-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/bff-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/bff-agent.md`
(bounded context, domain responsibilities, rules) -- read both first.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, httpx, or any downstream client.
- **No database, no migrations, no messaging** (ADR-0002 N/A -- this
  service owns no persisted business state; implementation plan
  section 2). Never add an event consumer/producer, an outbox, or an
  Alembic migration history here without first flagging
  `architecture-agent` -- if a requirement seems to need this service to
  react to an event, that event belongs in a domain service's own read
  model instead.
- One query handler (`application/queries/get_dashboard.py`), one public
  route (`GET /api/v1/bff/dashboard`), two HTTP clients
  (`infrastructure/external/`). No entities, no aggregates -- the domain
  layer is a single value object (`SectionStatus`) plus three port
  Protocols.
- Every downstream call is forwarded the incoming request's
  `Authorization` header UNCHANGED -- never re-derive, re-sign, or
  re-validate a JWT for a downstream call; the three downstream services
  already validate it themselves.

## Never do this

- Never write an `if` in `application/queries/get_dashboard.py` (or any
  future query handler here) that encodes a product rule rather than
  "did this call succeed, what shape did it come back in" -- that value
  belongs in the owning domain service's own API, added there in a
  separate, properly-scoped change. `tests/unit/application/test_get_dashboard.py`'s
  structural guardrail test enforces this by parsing the handler's own
  source for arithmetic/ordering-comparison operators.
- Never let one downstream call's failure raise through and fail the
  whole endpoint -- `asyncio.gather(..., return_exceptions=True)` is
  mandatory for any future multi-call handler added here; a failing
  dependency degrades only its own response section.
- Never share one circuit breaker across two unrelated downstream calls,
  even ones hitting the same host (see
  `infrastructure/external/nutrition_calculation_service_client.py`'s two
  independently named breakers for the precedent).
- Never make a live call to a real diary-service/nutrition-calculation-service
  in this service's own test suite -- `httpx.MockTransport` fixtures
  only.
- Never add a second aggregation endpoint without a new
  `/implementation-plan` -- this service is deliberately scoped to one
  endpoint as a clean reference implementation of the pattern.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s): `DiarySummaryPort`,
  `NutritionTotalsPort`, `NutritionTargetPort`.
- Adapters: `infrastructure/external/` (the two HTTP clients, each with
  its own circuit breaker(s)/retry/timeout/bulkhead).
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports. No DB engine, no broker
  connection, no background task -- `Container.startup()` is a no-op.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`. Hand-
  authored downstream response fixtures live in
  `tests/fixtures/downstream_responses/`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3).
