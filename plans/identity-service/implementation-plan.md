# Implementation Plan — `identity-service`

**Status:** Approved
**Date approved:** 2026-08-24
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0022 (Token Signing Scheme and JWKS Distribution), `/plans/platform-infra/implementation-plan.md`

## 1. Scope

Build `identity-service` end-to-end as the reference implementation for
every other NutriApp service: domain → application → infrastructure →
tests, plus its Terraform/Helm/CI wiring. This is the first service in the
repo, so it also establishes shared scaffolding (root `docker-compose.yml`,
`Makefile`, `.pre-commit-config.yaml`, `packages/shared-contracts/`,
`infra/k8s/charts/_lib/`) that every later service will reuse rather than
reinvent. (`infra/k8s/charts/_lib/` and the platform-level Terraform
modules are owned by the companion plan `/plans/platform-infra/implementation-plan.md`
— this plan only adds `infra/k8s/charts/identity-service/` and its own
Terraform variables on top of that foundation.)

**Bounded context** (per `.claude/agents/identity-agent.md`):
authentication, registration, session/token issuance & revocation,
authorization primitives (roles in tokens). No tenant lifecycle — NutriApp
is single-tenant B2C (ADR-0018).

**Acceptance criteria:**
1. `POST /api/v1/auth/register` creates a user (email + argon2-hashed
   password), publishes `UserRegistered` (v1) via the outbox, issues an
   email-verification token and includes its **reference id** (not the raw
   token) in the event payload.
2. `POST /api/v1/auth/verify-email` confirms a user's email via a
   time-limited, single-use token, obtained by the caller via the internal
   reveal endpoint (see section 5).
3. `POST /api/v1/auth/login` authenticates and issues a short-lived JWT
   access token (RS256, asymmetric-signed, carries `user_id` + `roles`)
   plus a revocable refresh token; rejects bad credentials with a generic
   error (no user-enumeration signal). Unverified or locked accounts are
   rejected regardless of password correctness.
4. `POST /api/v1/auth/refresh` exchanges a valid, non-revoked refresh token
   for a new access token (no rotation-on-use for v1).
5. `POST /api/v1/auth/logout` revokes the presented refresh token
   (idempotent — safe to call twice).
6. `POST /api/v1/auth/password-reset/request` and `/password-reset/confirm`
   implement reset without leaking account existence, using the same
   reference+secret pattern as email verification.
7. A public-key/JWKS endpoint (`/.well-known/jwks.json`) lets every other
   service verify tokens locally, without a synchronous call back to
   `identity-service` (Open Host Service pattern, per
   `docs/domain-glossary-and-context-map.md`, formalized in ADR-0022).
8. `register`, `login`, `password-reset/request` are rate-limited via
   Redis; **the rate limiter fails closed** — if Redis is unreachable,
   these endpoints reject with `503` rather than allowing requests through
   unchecked.
9. Every authn event (login success/failure, logout, password change,
   lockout, email verification, token reveal) is written to the immutable
   audit trail.
10. A new login from a device fingerprint not previously seen for that user
    publishes `NewDeviceLoginDetected`, using a simple heuristic (hash of
    User-Agent + IP); the user's very first login is not flagged as "new."
11. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70%
    (CLAUDE.md §3).

## 2. Architectural classification

Per ADR-0002 and `.claude/agents/identity-agent.md`: **conventional
persistence ("event-driven CRUD")** — state stored directly in normalized
tables, domain events published as a side effect via the Outbox pattern.
No event sourcing, no CQRS read models. All three hexagonal layers are
touched, since this is the first full scaffold of the pattern.

## 3. Files to create or modify

```
services/identity-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_identity_tables.py   # users, refresh_tokens,
                                                          # email_verification_tokens, password_reset_tokens,
                                                          # outbox, audit_log

  domain/
    entities/user.py
    value_objects/email.py
    value_objects/password.py
    value_objects/role.py                     # enum: USER, ADMIN
    value_objects/device_fingerprint.py        # hash(User-Agent + IP)
    events/user_registered.py
    ports/user_repository_port.py
    ports/password_hasher_port.py
    ports/token_issuer_port.py
    ports/token_repository_port.py
    ports/event_publisher_port.py
    ports/outbox_repository_port.py
    ports/audit_repository_port.py
    ports/rate_limiter_port.py
    services/registration_policy.py

  application/
    commands/register_user.py            (+ handler)
    commands/verify_email.py              (+ handler)
    commands/login.py                     (+ handler)
    commands/refresh_access_token.py      (+ handler)
    commands/logout.py                    (+ handler)
    commands/request_password_reset.py    (+ handler)
    commands/confirm_password_reset.py    (+ handler)
    commands/reveal_token_secret.py       (+ handler)  # internal, notification-service caller
    dto/

  infrastructure/
    http/routes/auth_routes.py
    http/routes/jwks_routes.py
    http/routes/internal_token_routes.py  # reveal endpoint
    http/schemas/
    http/health.py
    persistence/models.py
    persistence/postgres_user_repository.py
    persistence/postgres_token_repository.py
    persistence/postgres_outbox_repository.py
    persistence/postgres_audit_repository.py
    messaging/rabbitmq_event_publisher.py
    messaging/outbox_relay_worker.py
    security/argon2_password_hasher.py
    security/jwt_token_issuer.py
    cache/redis_rate_limiter.py           # fail-closed on Redis error
    composition_root.py
    main.py

  tests/
    unit/domain/..., unit/application/...
    integration/infrastructure/...
    contract/http/..., contract/events/...
    fixtures/factories.py

infra/k8s/charts/identity-service/
  Chart.yaml, values.yaml, values-dev.yaml, values-staging.yaml, values-prod.yaml
  templates/ (built on infra/k8s/charts/_lib/ from the platform-infra plan)

infra/terraform/environments/dev/identity-service.tf   # calls rds-service-database
                                                          # submodule (platform-infra plan) via a
                                                          # Kubernetes Job triggered from the Helm
                                                          # release, not a Terraform DB resource
                                                          # directly — see platform-infra plan §9.1

.github/workflows/identity-service-ci.yml

docker-compose.yml, .env.example, Makefile, .pre-commit-config.yaml   # first created here
packages/shared-contracts/schemas/user_registered.v1.json
packages/shared-contracts/schemas/password_reset_requested.v1.json    # new
packages/shared-contracts/schemas/new_device_login_detected.v1.json   # new
packages/shared-contracts/python/shared_contracts/events/
packages/shared-contracts/pyproject.toml

docs/events-catalog.md      # UserRegistered payload gains email_verification_token_reference_id;
                             # add PasswordResetRequested (v1), NewDeviceLoginDetected (v1)
docs/api-catalog.md         # /api/v1/auth: planned -> active once OpenAPI is generated
```

## 4. Ports/adapters affected

| Port (domain/application) | Adapter (infrastructure) |
|---|---|
| `UserRepositoryPort` | `PostgresUserRepository` |
| `PasswordHasherPort` | `Argon2PasswordHasher` |
| `TokenIssuerPort` | `JwtTokenIssuer` (RS256, JWKS exposure — per ADR-0022) |
| `TokenRepositoryPort` | `PostgresTokenRepository` (refresh/verification/reset tokens, reveal-once semantics) |
| `EventPublisherPort` | `RabbitMqEventPublisher` (faststream) |
| `OutboxRepositoryPort` | `PostgresOutboxRepository` + `OutboxRelayWorker` |
| `AuditRepositoryPort` | `PostgresAuditRepository` (append-only, `INSERT`-only DB role) |
| `RateLimiterPort` | `RedisRateLimiter` (fail-closed) |

All new — first service, nothing to reuse yet.

## 5. Domain events

- **`UserRegistered` (v1)** — payload gains one new field,
  `email_verification_token_reference_id`, to support the reference+secret
  pattern (decision: the raw verification/reset secret never travels in a
  published event; only a reference id does — `notification-service`
  retrieves the actual secret via a synchronous, once-only internal call,
  `POST /internal/v1/auth/tokens/{reference_id}/reveal`, authenticated
  service-to-service, wrapped in a circuit breaker on the caller's side).
  Additive change — `architecture-agent` to confirm it doesn't break the
  two existing documented consumers (`profile-service`, `diary-service`).
- **`PasswordResetRequested` (v1, new)** — `user_id`, `email`,
  `reset_token_reference_id`, `requested_at`. No raw secret.
- **`NewDeviceLoginDetected` (v1, new)** — `user_id`,
  `device_fingerprint_hash`, `occurred_at`, plus enough context for the
  alert email. No raw credentials.

All three require a `docs/events-catalog.md` update in the same PR, and
`architecture-agent` + `notification-agent` concurrence since they define
a new/changed cross-service contract.

## 6. Cross-service impact — flagged for `architecture-agent`

- The JWKS endpoint defines the token contract every future service
  depends on to validate tokens without a synchronous call back — this
  is now formalized in **ADR-0022** (Proposed, pending final architecture
  review).
- `PasswordResetRequested`/`NewDeviceLoginDetected` are new contracts for
  `notification-service`.
- The internal reveal endpoint introduces `identity-service`'s first
  synchronous inbound dependency from another service
  (`notification-service`) — that caller needs a circuit breaker per
  `.claude/skills/resilience-patterns/SKILL.md`, and the endpoint itself
  is never routed through Kong.
- Kong JWT-validation plugin configuration and `bff-service` claim
  forwarding are downstream consumers of this contract but don't exist
  yet — tracked as follow-up, out of scope here.

## 7. Resilience/caching/migration needs

- **Circuit breaker**: none needed for outbound calls from
  `identity-service` itself (it makes none synchronously in this scope).
  `notification-service`'s call to the reveal endpoint needs one on its
  side (see §6).
- **Rate limiting / Redis**: new key namespace
  `identity:ratelimit:{endpoint}:{ip_or_user}`, TTL = 1 minute (to be
  added to `.claude/skills/caching-strategy/SKILL.md`'s TTL table). **Fails
  closed**: a Redis error is surfaced as a typed exception the application
  layer maps to `503` on `register`/`login`/`password-reset/request` —
  deliberate availability/security trade-off, confirmed by the product
  owner over the "fail open" alternative.
- **Migration**: first Alembic migration, `CREATE TABLE`-only (users,
  tokens, outbox, audit_log) — additive by construction, does not trigger
  the destructive-change approval gate.
- **Terraform**: this plan's Terraform footprint is limited to
  `infra/terraform/environments/dev/identity-service.tf`, which does
  **not** create the service's database directly via Terraform — per the
  companion platform-infra plan's resolved design (see
  `/plans/platform-infra/implementation-plan.md` §9.1), the per-service
  database/role is created by a Kubernetes Job that runs as part of this
  service's Helm release, since Terraform's `postgresql` provider has no
  network path into the private-subnet RDS instance. This file only wires
  the service's chart to reference the shared RDS instance's outputs
  (host/port) and the Secrets Manager entry for its generated credentials.

## 8. Test plan reference

See `/plans/identity-service/test-plan.md` (approved).

## 9. Resolved decisions (formerly open questions)

1. **Token signing scheme** — documented in ADR-0022, decided directly
   rather than left open.
2. **Unverified users cannot log in** — confirmed.
3. **Reset/verification secret transport** — reference id in the event,
   raw secret via a synchronous internal reveal call. Confirmed.
4. **`NewDeviceLoginDetected` heuristic** — simple heuristic ships in v1:
   device fingerprint = hash(User-Agent + IP), compared against the user's
   known-device set; first-ever login is not flagged.
5. **Foundational infra** — a companion plan
   (`/plans/platform-infra/implementation-plan.md`) covers VPC, EKS, the
   shared RDS instance, ElastiCache, Secrets Manager baseline, and the
   `_lib` Helm chart. Approved alongside this plan.
6. **Rate limiter fallback** — fails closed (503) on Redis unavailability.
7. **Roles for v1** — `USER` and `ADMIN` only.
8. **RDS topology** — one shared RDS instance across all services; each
   service gets its own logical database within it, provisioned via a
   Kubernetes Job at Helm-release time (not via Terraform directly — see
   §7).

## Addendum — 2026-08-24, post-execution reconciliation

See `/plans/platform-infra/implementation-plan.md`'s matching addendum for
the full list of naming/wiring fixes made after both plans' execution
agents finished (they ran concurrently and disagreed on several output
and template names). On this plan's side specifically: `identity-service.tf`
now also provisions this service's own ECR repository
(`module.ecr_identity_service`, via the new generic
`infra/terraform/modules/ecr` module) and wires its URL into the Helm
release's `image.repository` — the `image.repository: identity-service`
placeholder in `values.yaml` was never a real, pullable reference until
this addendum. `image.tag` remains intentionally unset by Terraform, set
by `identity-service-ci.yml` at deploy time per the existing convention.

135 tests still pass (untouched by this reconciliation — only
infrastructure/Helm/Terraform files changed, no application code).

## Addendum 2 — 2026-08-24, `/implementation-review` + `/test-review`

`reviewer-agent` and `architecture-agent` ran independent review passes.
`architecture-agent`: **APPROVED WITH OBSERVATIONS** (4 documentation/
consistency notes, none blocking). `reviewer-agent`: **BLOCKED** — two
defects would have made `identity-service`'s own Helm chart fail to
render at all, and a third meant the audit-log INSERT-only guarantee
(CLAUDE.md §2.8) was decorative, not enforced. All three fixed directly:

1. **`serviceAccount.irsaRoleArn`** — `_lib`'s `_serviceaccount.tpl`
   requires this key at the top level; `identity-service.tf` was setting
   it nested under `serviceAccount.annotations` instead. Fixed in both
   `values.yaml` and `identity-service.tf`.
2. **`networkPolicy.ingressRules`** — `_lib`'s `_networkpolicy.tpl`
   requires raw Kubernetes `ingress` array entries; `values.yaml` used an
   invented `allowFrom`/`allowTo` shape `_lib` never consumed. Rewritten
   to the real shape; the non-functional `allowTo` (egress) block was
   dropped since `_lib` has no egress-rendering mechanism at all (flagged
   as a known `_lib`-level gap, not fixed here).
3. **Audit-log privilege separation, genuinely enforced** — the
   provisioning Job (`_db-provision-job.tpl`, running with sufficient
   privilege as RDS master) now creates the `identity_service_audit_writer`
   NOLOGIN role and grants it membership to the app's own role; the
   migration no longer attempts `CREATE ROLE` (it never had the
   privilege to). `Container.audit_engine`
   (`infrastructure/composition_root.py`) is a dedicated engine that
   opens every audit-write connection with `SET ROLE
   identity_service_audit_writer` (asyncpg `server_settings`) — a
   genuinely separate connection/session from the one shared by the
   other three repositories, never a role-switch on a shared session.
   Two new integration tests in `test_postgres_audit_repository.py`
   connect through this restricted engine and assert a real `UPDATE` is
   denied by Postgres, not just that a grant exists in metadata.

Also copied `_lib`'s `values.schema.json.template` into
`identity-service`'s own `values.schema.json` (per that library chart's
own README instruction) — this would have caught findings 1 and 2
automatically via `helm lint`; it didn't exist before this addendum.

Documentation follow-ups from `architecture-agent`'s observations, also
closed in this addendum: `docs/domain-glossary-and-context-map.md` gained
a row for the `notification-service -> identity-service` reveal-endpoint
exception; ADR-0022 moved from Proposed to **Accepted**, with
`docs/authorization-model.md` §2 now referencing it (the ADR's own exit
condition); `docs/events-catalog.md`'s three events are marked `Status:
Active` and the section heading no longer calls them "planned."

**Test count correction**: the actual count after this addendum's fixes
is **137 tests** (135 + 2 new privilege-enforcement tests), not the 135
stated in Addendum 1 — `qa-agent`'s independent `/test-review` re-ran the
suite itself rather than trusting this number and confirmed it.

`/test-review` verdict: **APPROVED WITH NOTES** (non-blocking follow-ups,
tracked here rather than silently dropped):
1. No test instantiates the real `Container` class against a live
   Postgres to prove `new_audit_session()` is privilege-restricted
   end-to-end — the existing tests independently reimplement the same
   `connect_args` mechanism rather than exercising `Container.__init__`
   itself, so a future typo there would go undetected. Recommended
   addition, not yet done.
2. No CI workflow runs `helm lint`/`helm template` for
   `infra/k8s/charts/identity-service` specifically (only `_lib` is
   covered by the platform-infra plan's own gate) — a real automation
   gap for `devops-agent`/`infra-agent` to close.
3. Mutation testing on `domain/entities/user.py` (lockout/verification
   state machine) and `domain/entities/token.py` (single-use/expiry
   logic) suggested as a future hardening step, not required.

Coverage after this addendum: domain 98.7%, application 97.9%,
infrastructure 89.4% — all above CLAUDE.md §3 thresholds.

**Follow-ups 1 and 2 above were resolved before human final approval**
(the human chose not to defer them):
1. `tests/integration/infrastructure/test_composition_root.py` (new) now
   constructs the real `Container` class against a live testcontainers
   Postgres and proves `container.new_audit_session()` is genuinely
   privilege-restricted — a real `UPDATE` attempt through it is denied by
   Postgres. This exercises `Container.__init__` itself, not a parallel
   reimplementation of its `connect_args`/`SET ROLE` mechanism.
2. `infra/k8s/charts/identity-service/ci/synthetic-values.yaml` (new,
   checked in) plus a `helm-lint-and-template` job added to
   `.github/workflows/identity-service-ci.yml` — `identity-service`'s own
   chart is now linted and templated in CI on every relevant change, not
   just `_lib`.

Follow-up 3 (mutation testing on `domain/entities/user.py` and
`domain/entities/token.py`) remains a suggested future hardening step,
not done.

**Final count after both fixes: 139 tests, 0 failures.** Coverage: domain
99%, application 98%, infrastructure 91%.
