# Testing Strategy

This document is the full specification behind the summary in CLAUDE.md section 3.
It is the reference `qa-agent` and every domain agent must follow.

## 1. Guiding Principle: TDD by Default

Red -> Green -> Refactor for every unit of behavior:
1. Write a failing test that expresses the desired behavior.
2. Write the minimum code to make it pass.
3. Refactor with the safety net of the passing test, without changing behavior.

Exceptions where writing the test first is impractical (pure scaffolding, generated
boilerplate, initial project structure) must be called out explicitly in the
implementation plan and approved by the human before proceeding.

## 2. Testing Pyramid

| Layer              | Target share | Scope                                                | Tooling                          |
|---------------------|--------------|--------------------------------------------------------|-----------------------------------|
| Unit                | ~70%         | Domain layer in isolation, no I/O, no framework          | `pytest`, `pytest-mock`            |
| Integration         | ~20%         | Adapters against real (containerized) infra              | `pytest`, `testcontainers`          |
| Contract            | covers all inter-service boundaries | API contracts + event schemas       | `pact-python` or JSON Schema-based checks |
| End-to-End (E2E)    | ~10%         | Critical user journeys, full stack                          | `pytest` + `httpx` against a running `docker-compose` stack, or Playwright for frontend flows |

### 2.1 Unit tests
- Test domain entities, value objects, and domain services directly, with no
  mocking of the domain itself.
- Application layer handlers are tested with fake/in-memory implementations of
  their ports (not real adapters) — fast, deterministic.
- No network calls, no real database, no real message broker.

### 2.2 Integration tests
- Test each adapter against a real dependency spun up via `testcontainers`
  (Postgres, RabbitMQ, Redis, Qdrant).
- Verify the adapter correctly implements its port's contract (round-trip a
  domain object through the real repository, publish and consume a real message).

### 2.3 Contract tests
- Every REST endpoint exposed to another service or to the frontend has a
  contract test verifying the response shape matches the documented OpenAPI
  schema.
- Every published domain event has a contract test verifying its payload matches
  the versioned JSON Schema in `docs/events-catalog.md`. Consumers test against
  the same schema to catch breaking changes early.

### 2.4 End-to-end tests
- Cover only the highest-value user journeys, kept deliberately small in number:
  - Register -> login -> perform the core action -> see updated summary.
  - Upload media (if applicable) -> receive detected items and estimated values ->
    confirm -> entry appears in the daily log.
  - Ask the AI chat assistant a question about the current week -> response is
    grounded in actual logged data (verified via a seeded fixture history).
- E2E tests run against a full `docker-compose` stack, not against mocks.

## 3. Coverage Targets (enforced in CI, per service)

| Layer            | Minimum line coverage |
|--------------------|--------------------------|
| Domain            | 90%                      |
| Application        | 85%                      |
| Infrastructure     | 70%                      |

- Coverage is measured with `pytest-cov` / `coverage.py`, per service, not
  aggregated across the whole monorepo (a well-tested service should not hide
  behind a poorly-tested one).
- A pull request that drops coverage below the threshold for the layer it
  touches is blocked at the `/test-review` gate.
- Coverage is a floor, not a target to game — `test-review` explicitly checks
  for tautological tests (asserting implementation details rather than
  behavior) and penalizes them even if they inflate the percentage.

## 4. Mutation Testing

- Recommended (not yet mandatory) for `nutrition-calculation-service`'s domain layer, given
  the correctness sensitivity of its core formulas (see
  `.claude/skills/domain-calculation-conventions/SKILL.md`). Tooling: `mutmut` or `cosmic-ray`.
- A mutation score below 80% on that specific module is a signal that the test
  suite is not actually pinning down correctness, even if line coverage looks
  high.

## 5. Test Data Strategy

- `factory_boy` factories for building domain objects and DTOs in tests, one
  factory module per service, kept next to the domain it builds.
- No shared mutable global fixtures across test files; prefer explicit,
  function-scoped fixtures.
- Seeded fixture datasets for E2E and manual QA live in
  `tests/fixtures/seed_data/` per service, versioned in git.

## 6. The Human-in-the-Loop Testing Gates

As defined in CLAUDE.md section 6, tests go through their own explicit gates,
separate from implementation gates:

- **`/test-plan`** — before any code is written, an agent lists the test cases
  it intends to write (happy path, edge cases, failure modes, contract tests
  if the change crosses a service boundary). The human approves this list
  before implementation starts.
- **`/test-execution`** — runs the full suite for the affected service(s) and
  reports pass/fail plus coverage deltas.
- **`/test-review`** — a review step (ideally by `qa-agent` or `reviewer-agent`,
  not the same agent that wrote the tests) that checks:
  - Do tests assert real behavior, not implementation details?
  - Are edge cases from the test plan actually covered?
  - Is coverage above threshold for the layer touched?
  - For event-sourced services: is there a test that rebuilds aggregate state
    purely from events and asserts the correct final state?

## 7. CI Enforcement

- Every pull request runs: unit -> integration -> contract tests for the
  affected service(s). E2E tests run on merge to the main integration branch
  (not on every PR, to keep feedback loops fast).
- A merge is blocked if: any test fails, coverage drops below threshold for a
  touched layer, or a contract test fails against a schema another service
  depends on.
- Full pipeline definition (path filtering, image scanning, deploy gates):
  see `docs/ci-cd-strategy.md`.

## 8. Load & Performance Testing

Deliberately out of scope for this document's functional pyramid. Load,
stress, soak, and spike testing — with their own SLO targets and their own
gate on prod promotion — are specified in `docs/performance-testing.md` and
`docs/observability-slo.md`.

## 9. Chaos & Resilience Testing

Also deliberately out of scope for the functional pyramid above: verifying
that the resilience patterns specified in CLAUDE.md section 2.6 (circuit
breakers, retries, timeouts) actually behave correctly **under real
failure**, not just in a unit test that mocks the failure. Full
specification: `docs/chaos-engineering.md`.
