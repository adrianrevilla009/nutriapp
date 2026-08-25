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

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s).
- Adapters: `infrastructure/persistence/`, `infrastructure/security/`,
  `infrastructure/messaging/`.
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`.
