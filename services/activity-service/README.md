# activity-service

NutriApp's manual exercise-logging service. This MVP builds **manual
exercise logging only** -- log/correct/delete/list exercise entries, each
publishing `ExerciseLogged` (v1) via the Outbox pattern. See
`.claude/agents/activity-agent.md` and `/plans/activity-service/implementation-plan.md`.

## Bounded context

Exercise logging and syncing exercise/calorie-burn data from third-party
wearable providers (Apple Health, Google Fit, Fitbit, Garmin), feeding
`nutrition-calculation-service`'s TDEE adjustment. See CLAUDE.md section
2.2. As of the 2026-09-11 addendum to
`/plans/activity-service/implementation-plan.md`, a Fitbit adapter exists
(mock-tested only, feature-flag gated off) -- see "Wearable sync
(Fitbit)" below. Apple Health, Google Fit, and Garmin remain interface-
only.

## Architecture

- Hexagonal (ADR-0001): `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only. The domain layer never imports FastAPI,
  SQLAlchemy, httpx, or aio_pika.
- **Event-driven CRUD** (ADR-0002 exception, confirmed by `architecture-agent`
  before `/plans/activity-service/implementation-plan.md` was written) --
  not event-sourced. `exercise_entries` is a conventional, soft-deleted
  table (one row per entry); `ExerciseLogged` is published via the Outbox
  pattern after every successful create or correction.
- `WearableProviderPort` (`domain/ports/wearable_provider_port.py`) is
  defined -- `connect`/`sync`/`disconnect` -- so a provider adapter has a
  settled contract to implement against without touching domain or
  application code (ADR-0001). **Fitbit is the only implementation.** See
  "Wearable sync (Fitbit)" and "Known limitations" below.

## Wearable sync (Fitbit)

Status as of the 2026-09-11 addendum to
`/plans/activity-service/implementation-plan.md` ("Fitbit adapter
(mocked, no real credentials) approved"):

- **Code exists**: `infrastructure/external/fitbit_provider_adapter.py`
  (`FitbitProviderAdapter`) implements `WearableProviderPort.connect`
  (OAuth 2.0 Authorization Code exchange), `.sync` (Activity Logs List,
  with token refresh when the stored token is expired), and `.disconnect`
  (local-state-first revoke, honoring "disconnection must be honored
  immediately" per `.claude/agents/activity-agent.md`). Resilience:
  two dedicated `purgatory` circuit breakers (OAuth vs. sync, isolated so
  one outage cannot trip the other), `tenacity` retry with backoff+jitter
  on the safe-to-retry `sync()` GET only (never on the single-use OAuth
  grants), explicit connect/read timeouts, and its own `httpx.AsyncClient`
  connection pool (bulkhead).

  | Circuit name | fail_max | reset_timeout |
  |---|---|---|
  | `fitbit_oauth` | 5 | 30s |
  | `fitbit_activities_sync` | 5 | 30s |
- **Tested exclusively against `httpx.MockTransport` fixtures** --
  `tests/integration/infrastructure/test_fitbit_provider_adapter.py` --
  never a live Fitbit call, because no real Fitbit developer account
  exists in this environment. **Unverified against the real Fitbit API.**
- **Feature-flag gated, off by default**:
  `Container.fitbit_provider` (`infrastructure/composition_root.py`)
  raises `WearableSyncDisabledError` unless BOTH
  `ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED=true` AND real-looking
  `ACTIVITY_SERVICE_FITBIT_CLIENT_ID`/`ACTIVITY_SERVICE_FITBIT_CLIENT_SECRET`
  values are configured (`ACTIVITY_SERVICE_FITBIT_REDIRECT_URI` is also
  read, defaulting to an empty string). All four default to
  off/empty in every environment, so in practice this raises
  unconditionally until a human provisions a real Fitbit developer
  account and configures real credentials. This is an env-var-based flag
  with the same boolean-gate shape Unleash would provide
  (`.claude/skills/feature-flags/SKILL.md`) -- a full Unleash SDK
  integration is deferred until `packages/feature-flags-client` exists
  (no service in this repo wires Unleash yet, same deferral as
  `food-recognition-service`'s `photo_analysis_enabled` flag); swapping
  it in later requires no change to `FitbitProviderAdapter` itself.
- **No application-layer consumer yet**: `Container.fitbit_provider` is
  reachable from the composition root only -- no HTTP route, command, or
  handler calls `connect`/`sync`/`disconnect` yet, and no dedup logic
  against manually logged entries exists. This addendum's scope was
  strictly the port implementation + feature-flag gate; wiring an actual
  connect/sync flow (routes, `WearableActivitySynced` publication,
  dedup-against-manual-entries) is future, separately-planned work.
- **Token storage is in-memory only**
  (`infrastructure/external/in_memory_wearable_token_store.py`) --
  process-local, non-persistent, acceptable only because no real
  connection can exist yet (feature flag off, no credentials). A durable,
  encrypted-at-rest store (per `docs/secrets-management.md`) is required
  before this can be enabled in any real environment.
- **No real Fitbit developer account exists in this environment.**
  Obtaining one, and completing the DPA/developer-terms compliance review
  in `docs/vendor-risk-register.md`, are human actions outside this
  addendum's scope -- see that document's Fitbit entry for current
  status.

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
  the Fitbit adapter's `sync()` method returns parsed activity data but
  does not itself publish this event (no application-layer consumer
  wires it yet -- see "Wearable sync (Fitbit)" above).
- **Consumed**: none -- this service has no inbound event dependency in
  this MVP.

## Known limitations

- **Fitbit is the only wearable provider with an adapter, and it is
  unreachable in every real deployment today.** `FitbitProviderAdapter`
  exists and is mock-tested (see "Wearable sync (Fitbit)" above) but is
  feature-flag gated off and requires real credentials that do not exist
  in this environment; Apple Health, Google Fit, and Garmin remain
  interface-only (zero adapters), pending developer account registration
  for each -- tracked in `docs/vendor-risk-register.md`. Do not build a
  feature that assumes any wearable data exists until a real Fitbit
  account is provisioned and the flag is deliberately enabled.
- **Deduplication between manual and wearable-synced entries is not
  implemented.** `.claude/agents/activity-agent.md`'s "never double-count"
  rule is not reachable without an application-layer consumer that calls
  `sync()` and dedupes against manual entries -- the Fitbit addendum's
  scope was strictly the port implementation, not this consumer, so it
  remains tracked as future work.
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

`tests/integration/infrastructure/test_fitbit_provider_adapter.py` and
the Fitbit-gating cases in `test_composition_root.py` live under
`tests/integration/` (mirroring `test_claude_vision_adapter.py`'s
convention) but need neither Docker nor real Fitbit credentials -- they
run against `httpx.MockTransport` and an in-memory `Settings`/`Container`
respectively. Only the DB/RabbitMQ-backed cases in that same directory
(persistence, messaging, `Container.startup`/`shutdown`, full HTTP
routes) require Docker.
