# identity-service

NutriApp's authentication, registration, session/token management, and
authorization service. Reference implementation for every other
microservice's hexagonal scaffold (CLAUDE.md section 14).

## Bounded context

Authentication, registration, email verification, login/logout,
session/token issuance and revocation, password reset, and the
role/permission model (`USER`/`ADMIN` only — CLAUDE.md's
authorization-model.md). No tenant lifecycle (NutriApp is single-tenant
B2C, ADR-0018).

## Token model (ADR-0022)

- **Access token**: short-lived (15 min default) JWT, RS256-signed,
  carries only `user_id` + `roles`. Not individually revocable — bounded
  by its own expiry.
- **Refresh token**: longer-lived (30 days default), opaque, stored
  server-side in Postgres, individually revocable (logout, password
  change, detected compromise). The only way to obtain a new access
  token.
- Public key published at `GET /.well-known/jwks.json` (RFC 7517) — every
  other service fetches and caches it to verify access tokens locally,
  without a synchronous call back to this service.

**These two token types have genuinely different persistence/verification
models — do not "simplify" them into one, see ADR-0022 consequences.**

## Reference + secret pattern

Email-verification and password-reset tokens never carry their raw secret
in a published domain event — only a `reference_id`. The raw secret is
retrieved once by `notification-service` via the internal, non-Kong-routed
endpoint `POST /internal/v1/auth/tokens/{reference_id}/reveal`, which is
single-use (replay-protected) and audited on every attempt.

## Running locally

```
docker compose up identity-service identity-db identity-redis rabbitmq
```

See root `docker-compose.yml` and `.env.example` for required environment
variables.

## Testing

```
cd services/identity-service
pip install -e ".[dev]"
pytest tests/unit                       # domain + application, no I/O
pytest tests/integration                # testcontainers: Postgres, Redis, RabbitMQ
pytest tests/contract                   # HTTP + event schema contracts
pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage targets (CLAUDE.md section 3): domain >= 90%, application >= 85%,
infrastructure >= 70%.

## Resilience configuration

- Rate limiting (Redis, fixed window, **fails closed** on Redis
  unavailability -> HTTP 503): `register`, `login`,
  `password-reset/request`. Key namespace
  `identity:ratelimit:{endpoint}:{ip}`, window 60s. Redis client:
  `socket_connect_timeout=2s`, `socket_timeout=2s` — a hung Redis fails
  fast into the same fail-closed path as a reachable-but-erroring one,
  rather than holding the request open indefinitely.
- `identity-service` makes no outbound synchronous calls itself in this
  scope, so it owns no circuit breakers. `notification-service`'s call
  into this service's internal reveal endpoint is `notification-service`'s
  circuit breaker to configure.
- **Audit-log privilege separation is enforced at the connection level**,
  not just decorated by a migration: `Container.audit_engine`
  (`infrastructure/composition_root.py`) opens every audit-write
  connection with `SET ROLE identity_service_audit_writer` (via asyncpg
  `server_settings`), a NOLOGIN role created by
  `infra/k8s/charts/_lib/templates/_db-provision-job.tpl` at
  provisioning time and granted INSERT-only on `audit_log` by
  `migrations/versions/0001_create_identity_tables.py`. See
  `tests/integration/infrastructure/test_postgres_audit_repository.py`
  for a test that actually attempts a real `UPDATE` through this
  restricted connection and asserts it's denied.

## Owned events (see docs/events-catalog.md)

- `UserRegistered` (v1) — additive: gained `email_verification_token_reference_id`.
- `PasswordResetRequested` (v1, new).
- `NewDeviceLoginDetected` (v1, new).

## Dependencies

- PostgreSQL (own logical database within the shared RDS instance).
- Redis (rate limiting).
- RabbitMQ (outbox relay -> `identity.events` topic exchange).
