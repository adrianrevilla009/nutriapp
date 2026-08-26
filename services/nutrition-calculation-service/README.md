# nutrition-calculation-service

NutriApp's macro/micronutrient totals and calorie/macro goal-setting
engine. Computes nutrient totals for diary entries/days from `diary-service`
and `catalog-service` data, and calorie/macro targets from `profile-service`
biometrics/goals via Mifflin-St Jeor. First service in the repo with three
simultaneous live inbound event dependencies (`diary-service`,
`profile-service`, `catalog-service`), and the first to maintain two
separate local, denormalized, read-only mirrors of other services' data
inside one service (implementation plan section 2).

## Bounded context

Pure computation/derivation service — owns no logging state, no product
data, and no auth. It reacts to three upstream producers' events and one
narrow synchronous call (see below) and publishes `NutritionValueRecomputed`/
`NutritionTargetUpdated`. See `.claude/agents/nutrition-calculation-agent.md`
and `.claude/skills/domain-calculation-conventions/SKILL.md` (mandatory
reading before touching the domain layer).

## Architecture

- Hexagonal (ADR-0001): `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only.
- **Event-driven CRUD** (ADR-0002 exception, confirmed by this service's
  agent doc and the cqrs-event-sourcing skill, not full event sourcing):
  `nutrition_targets`/`daily_nutrition_totals` are the current, conventional
  write model (upsert by natural key); `nutrition_target_history` is a
  separate append-only timeline. Every recompute still publishes via the
  Outbox pattern.
- Two local, denormalized, read-only mirrors of other services' data:
  `nutrient_panel_mirror` (from `catalog-service`'s `ProductCatalogued`/
  `ProductUpdated`) and metadata-only `user_metrics_snapshot` (from
  `profile-service`, via the reveal endpoint — never the raw biometric
  values, see "Security" below).
- Naming-translation seam (`domain/services/nutrient_vocabulary_translator.py`):
  this service defines its own canonical nutrient vocabulary and translates
  both `diary-service`'s and `catalog-service`'s differently-named raw
  shapes into it (implementation plan section 6(g)).

## The `profile-service` reveal endpoint (implementation plan Addendum 1)

`WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/`GoalUpdated` carry only
AES-256-GCM ciphertext (ADR-0023) — this service never decrypts them
itself. `RabbitMqProfileMetricsConsumer` treats them purely as a
recompute *trigger* (user_id + which field changed); the actual
recompute calls `ProfileRevealClient` -> `profile-service`'s
`POST /internal/v1/profile/{user_id}/reveal-metrics` (not built in this
worktree — see `services/nutrition-calculation-service`'s companion
sub-plan on `profile-service`'s side; this service only depends on the
documented HTTP contract).

- Dedicated `purgatory` circuit breaker (`fail_max=5`, `reset_timeout=30s`)
  — never shared with `profile-service`'s own internal KMS breaker.
- `tenacity` retry (3 attempts, exponential backoff+jitter) for transient
  transport errors only; explicit timeout (2s connect / 5s read).
- Own, isolated `httpx.AsyncClient` connection pool (bulkhead).
- On circuit-open or persistent failure (`ProfileRevealUnavailableError`):
  the recompute is deferred cleanly (logged, no crash, no
  `NutritionTargetUpdated` published) — never a guessed/defaulted
  biometric value.
- Per-caller service credential, sent as `X-Nutrition-Calc-Reveal-Credential`
  (env `NUTRITION_CALCULATION_SERVICE_PROFILE_REVEAL_CREDENTIAL`).

## Security — no plaintext biometric persistence (Addendum 1, requirement 8)

`user_metrics_snapshot` stores **metadata only**: `last_fetched_at`,
`formula_version`, `sex_constant_used`. It NEVER stores `weight_kg`/
`height_cm`/`age`/`sex` — those are fetched fresh from `ProfileRevealPort`
at each recompute and discarded immediately after use, so this table can
never become a second, unencrypted, non-crypto-shreddable copy of GDPR
Article 9 special-category data outside `profile-service`'s erasure design
(ADR-0023). Guarded by a schema-level negative test:
`tests/integration/infrastructure/test_postgres_user_metrics_snapshot_repository.py::test_schema_never_contains_a_plaintext_biometric_column`.

## Formulas (`.claude/skills/domain-calculation-conventions/SKILL.md`)

- **BMR** — Mifflin-St Jeor (Mifflin MD et al., *Am J Clin Nutr*, 1990).
  `Sex.OTHER` requires an explicit `calculation_sex_constant` selection,
  never defaulted (`domain/services/bmr_calculator.py`).
- **TDEE** — BMR × activity factor: `SEDENTARY=1.2, LIGHT=1.375,
  MODERATE=1.55, ACTIVE=1.725, VERY_ACTIVE=1.9` (`domain/services/tdee_calculator.py`).
- **Calorie target** — clamped: floor = BMR, deficit cap = 1000 kcal/day,
  surplus cap = 500 kcal/day; a clamp is always surfaced
  (`clamped`/`clamp_reason`), never silently honored
  (`domain/services/calorie_target_calculator.py`).
- **Macro repartition** — protein 1.6–2.2 g/kg, fat ≥ 20% of calories,
  carbs = remainder (floored at 0g, flagged via `carbs_floored`)
  (`domain/services/macro_repartition_calculator.py`).
- **Nutrient totals** — `(per_100g_value / 100) × quantity_grams`, summed
  per entry/day; micronutrients `"unavailable"` (never estimated) without
  a mirror match (`domain/services/nutrient_total_calculator.py`).

All computed results are informational estimates, never medical nutrition
therapy (CLAUDE.md section 8) — every query-layer DTO carries a
`disclaimer` field.

## Running locally

```
docker compose up nutrition-calculation-service nutrition-db nutrition-redis rabbitmq
```

See root `docker-compose.yml` and `.env.example`. Calling the real
`profile-service` reveal endpoint locally requires that endpoint to
actually exist on the `profile-service` image in use — this service
degrades to "recompute deferred" otherwise, per its documented fallback.

## Testing

```
cd services/nutrition-calculation-service
uv sync --extra dev
uv run pytest tests/unit                 # domain + application, no I/O
uv run pytest tests/integration          # testcontainers: Postgres, Redis, RabbitMQ
                                          # + httpx.MockTransport for ProfileRevealClient (never live)
uv run pytest tests/contract             # HTTP + event schema contracts
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage targets (CLAUDE.md section 3, agent doc): domain >= 90% (hard
floor), application >= 85%, infrastructure >= 70%. Mutation testing
(`mutmut`, domain layer only) is recommended, advisory/non-blocking in CI.

**`ProfileRevealClient` tests never make a live HTTP call** — exercised
against `httpx.MockTransport` fixture responses only
(`tests/integration/infrastructure/test_profile_reveal_client.py`), per
implementation plan Addendum 1's explicit requirement.

## Resilience configuration

- `ProfileRevealClient` (the only outbound synchronous call this service
  makes): `purgatory` circuit breaker, `fail_max=5`, `reset_timeout=30s`;
  `tenacity` retry, 3 attempts, exponential backoff+jitter, transient
  transport errors only; 2s connect / 5s read timeout. A 404/401/403/429
  response is a normal business response, not a health signal, and does
  not itself trip the breaker — only a transport failure or 5xx does.

## Caching (`.claude/skills/caching-strategy/SKILL.md`)

- `nutrition:current-target:{user_id}` — 1h TTL, invalidated on
  `NutritionTargetUpdated`.
- `nutrition:daily-total:{user_id}:{date}` — 5 min TTL (new namespace,
  added in this PR), invalidated on `NutritionValueRecomputed`.
- Both caches fail open on a Redis error (never make the read endpoint
  unavailable due to a cache-layer outage).

## Owned events (see docs/events-catalog.md)

- `NutritionValueRecomputed` (v1, new).
- `NutritionTargetUpdated` (v1, new).

## Consumed events

- `FoodEntryLogged` / `FoodEntryCorrected` / `FoodEntryDeleted` (diary-service).
- `WeightRecorded` / `BodyMetricRecorded` / `GoalSet` / `GoalUpdated` (profile-service, trigger only).
- `ProductCatalogued` / `ProductUpdated` (catalog-service).

## Dependencies

- PostgreSQL (own logical database within the shared RDS instance).
- Redis (`nutrition:*` key namespace on the shared ElastiCache cluster).
- RabbitMQ (3 inbound consumers + outbox relay -> `nutrition-calculation.events` exchange).
- `profile-service`'s internal reveal endpoint (synchronous, circuit-breaker-guarded).
