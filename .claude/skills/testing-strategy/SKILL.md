---
description: Implementation-level testing conventions (fixtures, naming, tooling) for NutriApp. Use whenever writing any test, in any service. For the full strategy rationale see docs/testing-strategy.md.
---

# Testing Strategy — Implementation Conventions

Full rationale and coverage targets in `docs/testing-strategy.md`. This skill
covers day-to-day implementation conventions.

## TDD Workflow
1. Write a failing test expressing the desired behavior (red).
2. Write the minimum code to pass it (green).
3. Refactor with the test as a safety net (refactor).
Do not write production code for a new behavior before its test exists,
except for explicitly-approved scaffolding (see CLAUDE.md section 3).

## Directory Layout (per service)
```
tests/
  unit/           # domain layer, no I/O
  integration/    # adapters against testcontainers-backed real dependencies
  contract/       # API and event schema contracts
  e2e/            # full-stack critical journeys
  fixtures/
    factories.py  # factory_boy factories
    seed_data/    # versioned fixture datasets for e2e/manual QA
```

## Naming Convention
`test_<unit_under_test>__<scenario>__<expected_outcome>`, e.g.:
```python
def test_core_action_handler__quantity_is_zero__raises_invalid_quantity_error():
    ...
```

## Fixtures & Factories
- Use `factory_boy` for building domain objects/DTOs. One factory module per
  service, colocated under `tests/fixtures/factories.py`.
- Prefer function-scoped fixtures; avoid shared mutable module/session-scoped
  state that can leak between tests.

## Unit Tests (domain layer)
- No mocking of the domain itself — construct real domain objects and assert
  on their behavior.
- No I/O: no real DB, no real HTTP, no real message broker, no real vector
  store, no real LLM/vision API call.

## Integration Tests (infrastructure layer)
- Use `testcontainers` to spin up real Postgres/RabbitMQ/Redis/Qdrant
  instances scoped to the test session.
- Assert the adapter correctly round-trips a domain object through the real
  dependency (write then read back; publish then consume).

## Contract Tests
- One contract test per public HTTP endpoint, asserting the response matches
  the documented OpenAPI schema.
- One contract test per published event, asserting the payload matches the
  schema version documented in `docs/events-catalog.md`. Consuming services
  test against the same schema.

## End-to-End Tests
- Run against a full `docker-compose` stack.
- Cover only the highest-value user journeys (see `docs/testing-strategy.md`
  section 2.4) — resist the temptation to add more; keep this layer small and
  fast to run.

## Coverage
- Measured per service with `pytest-cov`. Thresholds: domain >= 90%,
  application >= 85%, infrastructure >= 70% (see `docs/testing-strategy.md`).
- A high percentage achieved by testing trivial code while skipping real
  branches is not acceptable — `qa-agent` and `reviewer-agent` check what was
  actually exercised, not just the number.

## Mutation Testing
Recommended for `nutrition-calculation-service` domain layer (`mutmut`/`cosmic-ray`) given
correctness sensitivity of core domain formulas.
