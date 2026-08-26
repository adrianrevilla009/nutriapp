# profile-service

NutriApp's biometric/health metrics, goal-setting, and evolution-timeline
service. Full event sourcing + CQRS (ADR-0002) -- the second service in
the repo to use this pattern, and the concrete precedent `diary-service`
will mirror.

## Bounded context

Recording a user's biometric/health metrics (weight, height, age, sex,
activity level) and their stated goal (lose/maintain/gain, target value,
target date), and exposing the evolution timeline that powers the user
details panel's graphs. Created reactively for a user in response to
`UserRegistered` (v1), consumed from identity-service -- no synchronous
call back to identity-service. No authentication/registration/password
handling (identity-service's domain).

## Event sourcing model

- Write model: the `Profile` aggregate (`domain/entities/profile.py`) is
  never stored directly -- it is always derived by folding over its
  append-only event stream in `profile_events`
  (`infrastructure/persistence/postgres_event_store.py`).
- Read models: `profile_snapshot` (current state, one row per user) and
  `profile_evolution` (one row per metric-recording event, corrections
  appended as new rows, never overwritten) -- both disposable, rebuildable
  by replaying `profile_events`. Applied synchronously by command handlers
  in the same unit of work as the event append (see `CLAUDE.md` in this
  directory for the rationale/deviation note).
- A correction to a past value is always a new event -- `profile_events`
  rows are never mutated.

## Encryption / crypto-shredding readiness

`WeightRecorded.weight_kg`, `BodyMetricRecorded.value`, and
`GoalSet`/`GoalUpdated.target_value` are GDPR Article 9 special-category
values -- always encrypted (AES-256-GCM, per-user Data Encryption Key,
KMS-wrapped) before being appended to the event store, enqueued to the
outbox, or written into a read model. Per-user key material lives in
`profile_data_keys`, owned by this service
(`/plans/profile-service/implementation-plan.md` Addendum 1) -- **no
account-deletion/erasure endpoint is implemented yet** (plan section
9.2): this service is erasure-*ready* (destroying a user's key row would
make all their historical encrypted values permanently unreadable), not
erasure-*capable* until an upstream deletion-trigger event exists.

## Internal reveal-metrics endpoint (Addendum 2)

`POST /internal/v1/profile/{user_id}/reveal-metrics` -- service-to-service
only, called exactly once per BMR/TDEE calculation by
`nutrition-calculation-service`, which cannot decrypt this service's
per-user KMS-wrapped biometric data on its own (ADR-0023). See
`/plans/profile-service/implementation-plan.md` Addendum 2 for the full
rationale (a dedicated security-agent review found `identity-service`'s
`.../reveal` precedent -- single shared credential, no rate limit, no
audit trail -- insufficient for this endpoint's repeatedly-callable
Article 9 health data disclosure).

- **Never routed through Kong.** Served by a SEPARATE ASGI app
  (`infrastructure/main.py`'s `create_internal_app()`), listening on a
  distinct port (`PROFILE_SERVICE_INTERNAL_PORT`, default `8001`) from the
  public API (`PROFILE_SERVICE_PUBLIC_PORT`, default `8000`) -- a genuinely
  separate listening socket, not just a second allow-listed caller on the
  same port. Enforced at the `NetworkPolicy` level
  (`infra/k8s/charts/profile-service/values.yaml`): port 8001 is reachable
  only from `nutrition-calculation-service`'s pods, excluding Kong
  entirely; port 8000 remains Kong-only.
- **Per-caller credential**: the caller presents
  `X-Internal-Service-Credential`, compared via `hmac.compare_digest`
  against a distinct, Terraform-generated (`random_password`) credential
  (`PROFILE_SERVICE_REVEAL_CREDENTIAL_NUTRITION_CALC`) -- never
  identity-service's shared secret, never reused for any other caller.
  Wrong/missing credential -> `401`.
- **Rate limited**: keyed by a hash of the caller credential + `user_id`
  (`infrastructure/cache/redis_rate_limiter.py`, same fail-closed pattern
  as identity-service's `RedisRateLimiter`), default 30 requests/60s
  (`PROFILE_SERVICE_REVEAL_RATE_LIMIT` /
  `PROFILE_SERVICE_REVEAL_RATE_LIMIT_WINDOW_SECONDS`). Exceeding it ->
  `429`, and the KMS-decrypting `DataEncryptionPort` is never invoked for
  a throttled request. A Redis outage fails **closed** -> `503`, never an
  unlimited internal endpoint.
- **Response minimization**: exactly `weight_kg, height_cm, age, sex,
  activity_level, goal_type` -- a dedicated query
  (`application/queries/get_biometric_snapshot_for_calculation.py`), never
  a wrapper around the full-profile snapshot (which also carries
  `consent_granted`, `goal_target_value`, `goal_target_date`).
- **Audit trail** (this service's first -- `domain/entities/audit_record.py`,
  `infrastructure/persistence/postgres_audit_repository.py`): every call,
  success or failure, writes exactly one append-only row to
  `audit_records` (`action="biometric_snapshot_revealed"`,
  `target_type="profile"`, `target_id=user_id`, `outcome`,
  `metadata={"fields": [...]}` on success or `{"reason": ...}` on failure
  -- field NAMES only, never a raw biometric VALUE), via a dedicated DB
  role (`profile_service_audit_writer`) granted INSERT-only, exactly like
  identity-service's `audit_log`.
- **No field value ever logged**: structured logs record that a reveal
  occurred, the `user_id`, the outcome, and (on success) the field NAMES
  revealed -- never a numeric/enum VALUE. See
  `tests/contract/http/test_internal_reveal_metrics_routes.py`'s
  log-redaction test.

## Authentication

Per ADR-0022 and `docs/authorization-model.md` section 2: every request
carries an `Authorization: Bearer <token>` header with a RS256 JWT issued
by `identity-service`. This service verifies the token's signature and
expiry **locally**, using the shared
`shared_contracts.auth.jwt_verifier.JwtVerifier`
(`packages/shared-contracts/python/shared_contracts/auth/jwt_verifier.py`)
against `identity-service`'s published JWKS
(`/.well-known/jwks.json`, cached with a bounded TTL) --
**no synchronous call back to identity-service on every request**, only on
a JWKS cache miss/expiry. See
`infrastructure/http/dependencies.py`'s `get_authenticated_user_id` for
the FastAPI wiring. A missing/malformed/expired/tampered token, or a
JWKS-fetch failure, all fail closed as `401`.

## Running locally

```
docker compose up profile-service profile-db profile-redis rabbitmq
```

The container runs `python -m infrastructure.main` (not a bare `uvicorn
infrastructure.main:app`), which serves the public API and the internal
reveal-metrics API concurrently, on two distinct ports, in one process
(`infrastructure/main.py`'s `run()`).

See root `docker-compose.yml` for required environment variables
(`PROFILE_SERVICE_DATABASE_URL`, `PROFILE_SERVICE_RABBITMQ_URL`,
`PROFILE_SERVICE_KMS_KEY_ID`, `PROFILE_SERVICE_KMS_ENDPOINT_URL` for local
LocalStack/moto use, `PROFILE_SERVICE_IDENTITY_JWKS_URL` /
`PROFILE_SERVICE_IDENTITY_ISSUER` for the JWT verifier -- defaults to
`http://identity-service:8000/.well-known/jwks.json` / `identity-service`,
matching the docker-compose service name; `PROFILE_SERVICE_REDIS_URL`,
`PROFILE_SERVICE_REVEAL_CREDENTIAL_NUTRITION_CALC`,
`PROFILE_SERVICE_PUBLIC_PORT` / `PROFILE_SERVICE_INTERNAL_PORT` for the
reveal-metrics endpoint, Addendum 2).

## Testing

```
cd services/profile-service
pip install -e ".[dev]"
pytest tests/unit                       # domain + application, no I/O
pytest tests/integration                # testcontainers: Postgres, RabbitMQ; moto for KMS
pytest tests/contract                   # HTTP + event schema contracts
pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage targets (CLAUDE.md section 3): domain >= 90%, application >= 85%,
infrastructure >= 70%.

## Read-model rebuild (runbook)

`profile_snapshot` and `profile_evolution` are disposable projections --
they can always be rebuilt from `profile_events`, the source of truth. To
actually do so (e.g. after a projector bug is fixed and historical rows
need to be reprojected, or to stand up a fresh read-model database):

```
cd services/profile-service
PROFILE_SERVICE_DATABASE_URL=postgresql+asyncpg://... python -m scripts.rebuild_read_models
```

This truncates both read-model tables and replays every row in
`profile_events`, grouped by aggregate (`user_id`) and ordered
chronologically within each aggregate, through the same `apply()` methods
the command handlers already call synchronously on every write --
`scripts/rebuild_read_models.py`. `PostgresEvolutionProjector.apply()` is
idempotent under replay (`ON CONFLICT (source_event_id) DO NOTHING`,
migration `0002`), so re-running this script never produces duplicate
`profile_evolution` rows even if run twice back to back. Do not run this
against a database with concurrent writers without first pausing the
write path -- see the script's module docstring.

## Resilience configuration

This service has two synchronous external dependencies: AWS KMS (envelope
encryption) and identity-service's JWKS endpoint (JWT verification, fetched
only on a cache miss/expiry, not per request). Each gets its own,
independently configured circuit breaker (`.claude/skills/resilience-patterns/SKILL.md`
-- never share one breaker across unrelated dependencies).

- KMS (`GenerateDataKey`/`Decrypt`) is wrapped in a dedicated `pybreaker`
  circuit breaker (`fail_max=5`, `reset_timeout=30s`), a bounded `tenacity` retry
  (3 attempts, exponential backoff with jitter, `initial=0.1s`/`max=1.0s`)
  inside the breaker's failure counting, and two distinct, deliberately
  separate timeouts (`infrastructure/security/kms_envelope_data_encryption.py`,
  `infrastructure/composition_root.py`) -- fixed at `/implementation-review`
  after the original single 2s timeout wrapped the *entire* retry
  sequence, meaning a slow single attempt could starve every retry and
  misreport genuine retry-exhaustion as a bare timeout:

  | Timeout | Value | Bounds | Enforced by |
  |---|---|---|---|
  | Per-attempt | 2.0s | one KMS `GenerateDataKey`/`Decrypt` call | `botocore.config.Config(connect_timeout=2.0, read_timeout=2.0)` on the real `boto3` client (`composition_root.py`); botocore's own retries disabled (`max_attempts=1`) so `tenacity` is the sole retry authority |
  | Overall | 9.0s | the whole breaker+retry sequence (up to 3 attempts + up to 2 backoff waits) | `asyncio.wait_for` around `breaker(retrying(fn))` (`kms_envelope_data_encryption.py`) |

  Worst case is `3 * 2.0s + 2 * 1.0s = 8.0s`, so the 9.0s overall timeout
  leaves a 1.0s margin -- a genuine retry-exhaustion failure now correctly
  surfaces as `KmsCallFailedError` after retries actually ran, not as a
  premature `TimeoutError`. A call made while the circuit is open fails
  fast with `KmsCircuitOpenError` rather than blocking. First-use DEK
  generation for a brand-new user is safe under concurrency: two
  concurrent first-use requests race an `INSERT ... ON CONFLICT (user_id)
  DO NOTHING` on `profile_data_keys`; the losing request re-reads and
  unwraps the winner's key instead of persisting/using a second one.
- identity-service's JWKS endpoint (`GET /.well-known/jwks.json`, fetched
  only on a JWKS cache miss/expiry -- not per verified request) is wrapped
  in its own dedicated `pybreaker` circuit breaker (`fail_max=5`,
  `reset_timeout=30s`) and the same `tenacity` retry shape as KMS (3
  attempts, exponential backoff with jitter), inside the breaker's failure
  counting (`packages/shared-contracts/python/shared_contracts/auth/jwt_verifier.py`).
  Per-attempt timeout: 2.0s (the injected `httpx.Client`'s own `timeout`).
  Overall timeout bounding the whole breaker+retry sequence: 9.0s (same
  `3*2.0 + 2*1.0 = 8.0s` worst-case math as KMS, 1.0s margin). The JWKS
  document itself is cached in-process with a 10-minute TTL
  (`.claude/skills/caching-strategy/SKILL.md`) so key rotation is picked
  up periodically, not just once at startup. A missing/invalid/expired
  token, or a JWKS-fetch failure/open circuit, all fail closed as `401`
  (`infrastructure/http/dependencies.py`).
- `processed_inbound_events` dedup TTL: 7 days -- comfortably longer than
  any realistic RabbitMQ redelivery window, short enough that a periodic
  cleanup (follow-up, not implemented) keeps the table bounded.
- `UserRegistered` consumer: failed messages are retried up to 5 times
  (`x-profile-retry-count` header, manually incremented on republish),
  then routed to `profile-service.user_registered.dlq` instead of being
  retried forever or dropped silently.
- Reveal-metrics rate limiter (Redis, `PROFILE_SERVICE_REDIS_URL`) has its
  own client/connection pool (bulkhead), independent of the DB/KMS/RabbitMQ
  resources above -- a Redis outage's blast radius is scoped to that one
  internal endpoint. `RedisRateLimiter` fails **closed** (`503`) on any
  `RedisError`, including a timeout (`socket_connect_timeout=2`,
  `socket_timeout=2`) -- never treated as "no limit".

## Owned events (see docs/events-catalog.md)

- `ProfileCreated` (v1) -- internal, not published to other services'
  documented consumers (no external consumer needs it yet).
- `BiometricConsentGranted` (v1).
- `WeightRecorded` (v1) -- `weight_kg` encrypted.
- `BodyMetricRecorded` (v1) -- `value` encrypted.
- `GoalSet` / `GoalUpdated` (v1) -- `target_value` encrypted.

## Consumed events

- `UserRegistered` (v1) from identity-service -- creates an empty profile
  aggregate for that `user_id`. Idempotent by `event_id`.

## Dependencies

- PostgreSQL (own logical database within the shared RDS instance).
- AWS KMS (per-user envelope encryption key wrapping).
- RabbitMQ (outbox relay -> `profile.events` topic exchange;
  consumes identity-service's `identity.events` exchange).
- Redis (shared ElastiCache cluster, `profile:*` key namespace) --
  reveal-metrics rate limiting only (Addendum 2).
