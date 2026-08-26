# profile-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/profile-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/profile-agent.md`
(bounded context, domain responsibilities, rules) -- read both first.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001).
- Full event sourcing + CQRS (ADR-0002) -- NOT conventional persistence.
  The `Profile` aggregate (`domain/entities/profile.py`) is always derived
  by folding over its event stream (`rebuild`); `profile_snapshot` and
  `profile_evolution` are disposable read models, rebuildable by replaying
  `profile_events`.
- Never mutate a row in `profile_events` -- a correction is always a new
  event, appended, never an UPDATE.
- Encryption: `WeightRecorded.weight_kg`, `BodyMetricRecorded.value`, and
  `GoalSet`/`GoalUpdated.target_value` are ALWAYS encrypted before they
  are appended to `profile_events`, enqueued to the outbox, or written
  into a read model (`application/dto/event_crypto.py` is the one place
  that knows which fields). The domain layer (`domain/entities/profile.py`,
  `domain/events/*.py`) only ever sees PLAINTEXT -- zero I/O in that layer
  (ADR-0001) -- encryption/decryption is entirely an application-layer
  responsibility, via `DataEncryptionPort`.
- Per-user key material: `profile-service` owns its own KMS-wrapped data
  keys (`profile_data_keys` table), per
  `/plans/profile-service/implementation-plan.md` Addendum 1 -- not a
  shared/centralized key store.
- Projection consistency (deviation from the "async projector subscribing
  to RabbitMQ" default described in cqrs-event-sourcing SKILL.md, flagged
  for architecture-agent review): `PostgresSnapshotProjector` and
  `PostgresEvolutionProjector` are applied SYNCHRONOUSLY by command
  handlers, in the same DB session/transaction as the event-store append
  and outbox enqueue -- not via a separate RabbitMQ-subscribing projector
  process. This keeps `GET /profile` immediately consistent with a prior
  write from the same client and avoids a third long-running consumer
  process in this service's first cut. Both read models remain fully
  disposable/rebuildable by replaying `profile_events` through the same
  `apply()` method (proven by the projector-replay integration tests) --
  only the trigger for when that replay happens differs from the
  "eventually consistent via broker" default.
- Authentication (ADR-0022): every request's `Authorization: Bearer
  <token>` header carries a RS256 JWT issued by identity-service, verified
  **locally** by this service via
  `shared_contracts.auth.jwt_verifier.JwtVerifier`
  (`packages/shared-contracts/python/shared_contracts/auth/jwt_verifier.py`
  -- `profile-service` is its first consumer), which fetches + caches
  (10-minute TTL) identity-service's published JWKS
  (`/.well-known/jwks.json`). No synchronous call back to identity-service
  on every request, only on a JWKS cache miss/expiry -- see
  `infrastructure/http/dependencies.py`'s `get_authenticated_user_id`.

## Internal reveal-metrics endpoint (Addendum 2)

`POST /internal/v1/profile/{user_id}/reveal-metrics` is a SEPARATE,
security-sensitive surface -- read `README.md`'s dedicated section before
touching anything under `infrastructure/http/routes/internal_reveal_metrics_routes.py`,
`application/queries/get_biometric_snapshot_for_calculation.py`,
`domain/entities/audit_record.py`, or `infrastructure/cache/`. Non-negotiable
invariants specific to this endpoint (all 8 requirements in
`/plans/profile-service/implementation-plan.md` Addendum 2 are binding,
not advisory):

- Never let this endpoint's route/handler decrypt or return any field
  beyond the exact 6 allow-listed in `REVEALED_FIELDS`
  (`get_biometric_snapshot_for_calculation.py`) -- not even by "helpfully"
  reusing `GetProfileSnapshotHandler`.
- Every call (success AND failure) writes exactly one `AuditRecord` via
  `AuditRepositoryPort` -- `domain/entities/audit_record.py`'s
  `__post_init__` rejects metadata containing a biometric value key as a
  backstop, but do not rely on that backstop instead of getting the
  call site right.
- The rate limiter check happens BEFORE any call to `DataEncryptionPort` --
  a throttled request must never reach KMS.
- Never add a public (Kong-routed) route to `infrastructure/main.py`'s
  `create_internal_app()`, and never add this endpoint's router to
  `create_app()` (the public app) -- the two-port/two-app split is the
  actual security boundary, not just the NetworkPolicy.
- This is this service's first audit-trail capability -- `audit_records`
  is genuinely append-only via a dedicated Postgres role
  (`profile_service_audit_writer`, INSERT-only), not just an
  application-level convention.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s).
- Adapters: `infrastructure/persistence/`, `infrastructure/security/`,
  `infrastructure/cache/` (Redis rate limiter, reveal-metrics only),
  `infrastructure/messaging/`.
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`.
