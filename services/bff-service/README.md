# bff-service

Frontend response aggregation only -- orchestration, never business logic
(ADR-0008). Sits behind Kong (edge concerns: TLS, rate limiting, JWT
signature validation, CORS -- Kong's job, not this service's) and
composes a single response for a specific frontend screen by calling
downstream domain services in parallel.

## Bounded context

See `.claude/agents/bff-agent.md`. The one rule that matters more than
any other: this service contains orchestration, never business logic. If
a change needs a computed/business value, it belongs in the owning
domain service's own API, never here.

## Architecture

Hexagonal (`domain/` -> `application/` -> `infrastructure/`, ADR-0001),
but unusually thin: **no database of its own for business state**, **no
domain events published or consumed** (implementation plan section 2).
Ports here are downstream HTTP-client ports
(`DiarySummaryPort`/`NutritionTotalsPort`/`NutritionTargetPort`), not
repositories. The one query handler, `GetDashboardHandler`, fans out
three parallel calls and reshapes the results -- structural mapping only,
enforced by `tests/unit/application/test_get_dashboard.py`'s structural
"no business logic" guardrail test.

## Public API

- `GET /api/v1/bff/dashboard?date={date}` -- the authenticated user's
  home/dashboard screen (CLAUDE.md's E2E journey 1). Fans out, in
  parallel:
  - `diary-service`: `GET /api/v1/diary/summary?date={date}`
  - `nutrition-calculation-service`: `GET /api/v1/nutrition/totals/{date}`
  - `nutrition-calculation-service`: `GET /api/v1/nutrition/target`

  All three are already-public, already-Kong-routable endpoints -- this
  service calls them server-to-server purely to do the fan-out/
  composition the frontend would otherwise do itself in three separate
  requests (Open Host Service / Customer-Supplier,
  `docs/domain-glossary-and-context-map.md`). The incoming request's
  `Authorization` header is forwarded UNCHANGED to all three calls.

Each downstream call degrades independently on failure: the response is
always `200`, with the affected section marked
`{"status": "unavailable", "reason": "downstream_error"}`. The target
call has one additional, EXPECTED (non-error) case:
`{"status": "unavailable", "reason": "not_yet_computed"}`, for
nutrition-calculation-service's documented `Sex.OTHER`/deferred-recompute
gap (see that service's `README.md`) -- a well-formed `404`, never
treated as a failure.

## Resilience

Three independent downstream calls, each its own named `purgatory`
circuit breaker (`.claude/skills/resilience-patterns/SKILL.md`) -- the
two nutrition-calculation-service calls get separate breakers despite
sharing a host and an `httpx.AsyncClient` connection pool, since their
failure modes are unrelated:

| Integration                                  | Circuit name        | fail_max | reset_timeout | Timeout (connect/read) |
|-----------------------------------------------|-----------------------|-----------|------------------|---------------------------|
| diary-service summary                          | `diary_summary`        | 5         | 30s                | 1s / 3s                     |
| nutrition-calculation-service totals            | `nutrition_totals`     | 5         | 30s                | 1s / 3s                     |
| nutrition-calculation-service target            | `nutrition_target`     | 5         | 30s                | 1s / 3s                     |

Each call also has a `tenacity` retry (3 attempts, exponential backoff +
jitter, transport errors only -- all three are GETs, unconditionally safe
to retry). Timeouts are tighter than a typical write-path call since this
is a synchronous, user-waiting dashboard load.

## No caching layer of its own

Each downstream service already caches (diary-service's Redis cache,
nutrition-calculation-service's caches) -- this service always makes a
live call; double-caching the same data here would be redundant
staleness risk for no benefit at this scale.

## Testing

`docs/testing-strategy.md`. Both downstream clients are tested against
`httpx.MockTransport` fixtures -- never a real diary-service/
nutrition-calculation-service call in this service's own test suite. Run:

```
uv run pytest tests/unit -q
uv run pytest tests/integration tests/contract -q
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage floors: domain >= 90%, application >= 85%, infrastructure >= 70%.

## Local/dev authentication note

In a real deployment, Kong validates the JWT signature at the edge
before a request ever reaches this service. `infrastructure/http/dependencies.py`
reuses `packages/shared-contracts`' centralized JWT auth dependency
purely so a request made directly against this service (bypassing Kong,
e.g. in `docker-compose` or a test) still gets a proper `401` -- this is
a narrow local/dev convenience, not this service taking on Kong's edge
responsibility.
