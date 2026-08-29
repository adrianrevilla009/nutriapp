# activity-service

NutriApp's manual exercise-logging service. This MVP builds **manual
exercise logging only** -- log/correct/delete/list exercise entries, each
publishing `ExerciseLogged` (v1) via the Outbox pattern. See
`.claude/agents/activity-agent.md` and `/plans/activity-service/implementation-plan.md`.

## Bounded context

Exercise logging and (in a future, separately-planned addition) syncing
exercise/calorie-burn data from third-party wearable providers (Apple
Health, Google Fit, Fitbit, Garmin), feeding `nutrition-calculation-service`'s
TDEE adjustment. See CLAUDE.md section 2.2.

## Architecture

- Hexagonal (ADR-0001): `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only. The domain layer never imports FastAPI,
  SQLAlchemy, or aio_pika.
- **Event-driven CRUD** (ADR-0002 exception, confirmed by `architecture-agent`
  before `/plans/activity-service/implementation-plan.md` was written) --
  not event-sourced. `exercise_entries` is a conventional, soft-deleted
  table (one row per entry); `ExerciseLogged` is published via the Outbox
  pattern after every successful create or correction.
- `WearableProviderPort` (`domain/ports/wearable_provider_port.py`) is
  defined -- `connect`/`sync`/`disconnect` -- so a future provider adapter
  has a settled contract to implement against without touching domain or
  application code (ADR-0001). **Zero adapters are implemented.** See
  "Known limitations" below.

## Endpoints

- `POST /api/v1/activity/exercises` -- log a manual exercise entry.
- `PATCH /api/v1/activity/exercises/{entry_id}` -- correct a previously
  logged entry (partial update; only fields present in the request body
  are changed).
- `DELETE /api/v1/activity/exercises/{entry_id}` -- soft-delete an entry
  (idempotent: deleting an already-deleted entry returns `204` again, not
  `404`).
- `GET /api/v1/activity/exercises?date={date}` -- list the authenticated
  user's entries for a given date.

Authentication: `shared_contracts.auth` (ADR-0022) -- every request's
`Authorization: Bearer <token>` header carries an RS256 JWT verified
locally against `identity-service`'s published JWKS.

## Events

- **Published**: `ExerciseLogged` (v1) -- see `docs/events-catalog.md`.
  Consumers `nutrition-calculation-service`/`analytics-service` are
  documented but not yet wired to consume it (see "Known limitations").
- **Documented, not yet implemented**: `WearableActivitySynced` (v1) --
  no adapter exists to publish it yet.
- **Consumed**: none -- this service has no inbound event dependency in
  this MVP.

## Known limitations

- **No wearable provider is implemented yet.** `WearableProviderPort` is
  defined in the domain layer (interface only), but zero of the four
  providers (Apple Health, Google Fit, Fitbit, Garmin) have an adapter,
  pending developer account registration for each -- tracked in
  `docs/vendor-risk-register.md`. Do not build a feature that assumes any
  wearable data exists until this is resolved.
- **Deduplication between manual and wearable-synced entries is not
  implemented.** `.claude/agents/activity-agent.md`'s "never double-count"
  rule is not reachable without a wearable adapter to dedupe against --
  tracked as part of the future wearable-integration work, not this MVP.
- **`ExerciseLogged` has no real consumer yet.** TDEE adjustment
  (`NutritionTargetUpdated`'s `activity_adjustment_kcal`, currently always
  `null`) remains a documented future addition to
  `nutrition-calculation-service` -- wiring a real consumer means
  reopening that already-merged, already-closed service, which its own
  `CLAUDE.md` gates behind a new ADR for any change to its formula
  surface. Same deferral shape as `analytics-service`'s
  `NutrientDeficiencyDetected` consumption.
- **No calorie-burn auto-estimation.** `calories_burned_kcal` is a
  required field the user supplies explicitly -- no duration x MET-style
  estimate is computed. A future auto-estimation formula would be a real
  domain calculation in its own right
  (`.claude/skills/domain-calculation-conventions/SKILL.md`), not a
  small addition to this service.

Per `.claude/agents/activity-agent.md`'s rule: a calorie-burn figure is
never presented as more precise than its source claims -- in this MVP it
is always the user's own estimate, never silently upgraded to a
provider-reported figure.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3).

## Running locally

```
docker compose up activity-service activity-db rabbitmq
```

See root `docker-compose.yml` and `.env.example`.

## Testing

```
cd services/activity-service
uv sync --frozen --extra dev --no-build
uv run pytest tests/unit -q
uv run pytest tests/integration tests/contract -q   # needs Docker (testcontainers)
uv run pytest tests/unit tests/contract tests/integration --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```
