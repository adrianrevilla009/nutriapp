# Test Plan — `identity-service` (+ infra validation gates)

**Status:** Approved
**Date approved:** 2026-08-24
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/identity-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD
(`.claude/skills/testing-strategy/SKILL.md`). A few implementation details
had to be pinned down to write concrete cases; flagged inline with
**(assumption)**.

## 1. Unit test cases

### Domain layer (no mocking, no I/O)

**Value Objects**
- `Email`: valid format accepted, normalized to lowercase.
- `Email`: invalid format (no `@`, empty, no domain) raises `InvalidEmailError`.
- `Password`: meets length/complexity policy accepted.
- `Password`: too short, or missing a required character class, raises `WeakPasswordError`.
- `Password`: plaintext never appears in `repr()`/`str()`.
- `Role`: only `USER`/`ADMIN` valid; unknown value raises.

**`User` aggregate**
- Registration produces a user in `PENDING_VERIFICATION` status.
- `verify_email()` transitions `PENDING_VERIFICATION` → `ACTIVE`.
- `verify_email()` on an already-`ACTIVE` user raises `AlreadyVerifiedError`.
- Login attempt on `PENDING_VERIFICATION` user raises `EmailNotVerifiedError`.
- Failed-login counter increments on `record_login_failure()`.
- 5th consecutive failure transitions status to `LOCKED` **(assumption: threshold = 5)**.
- Login attempt on `LOCKED` user raises `AccountLockedError`, regardless of password correctness.
- `record_login_success()` resets the failed-attempt counter and updates `last_login_at`.
- `change_password()` replaces the hash and stamps a `password_changed_at` fact (used later to mass-revoke refresh tokens).
- Role assignment only allows `USER↔ADMIN`; unknown role rejected.

**Device fingerprint / new-device heuristic**
- Same `(User-Agent, IP)` input always produces the same fingerprint hash.
- A user's very first login marks the device known **without** flagging "new device."
- A fingerprint not in the user's known-device set is correctly identified as new.

**Tokens (refresh / email-verification / password-reset)**
- `is_expired()` is false before TTL, true after (clock injected, no real sleeping).
- `mark_used()` then a second use attempt raises `TokenAlreadyUsedError`.
- Verifying an expired token raises `TokenExpiredError`.

### Application layer (fake/in-memory ports)

**`RegisterUserHandler`**
- Valid input: user persisted, `UserRegistered` enqueued to the outbox in the same unit of work.
- Duplicate email (case-insensitive): rejected with `EmailAlreadyRegisteredError`, nothing persisted.
- Weak password: rejected before any repository call.
- Success path issues an email-verification token and includes only its **reference id** in the `UserRegistered` payload — never the raw token.

**`VerifyEmailHandler`**
- Valid token: user → `ACTIVE`, audit record `email_verified`/success.
- Unknown, expired, or already-used token: rejected, audit record `email_verified`/failure — same generic error shape for all three.

**`LoginHandler`**
- Correct credentials, verified, unlocked: issues access + refresh token pair, audit `login`/success.
- Wrong password **and** unknown email: identical generic "invalid credentials" error (enumeration guard) — one test asserting both produce the same response shape.
- Unverified / locked account: rejected, audit `login`/failure with the specific reason (internal/audit-only, never in the response).
- Rate limit exceeded: rejected before touching the repository, audit `login`/failure reason=`rate_limited`.
- Login from an unrecognized device fingerprint: `NewDeviceLoginDetected` published in addition to the normal success path.
- Login from a known fingerprint: no `NewDeviceLoginDetected`.

**`RefreshAccessTokenHandler`**
- Valid, non-revoked, non-expired refresh token: issues a new access token; the refresh token itself is **not** rotated **(assumption: no rotate-on-use — v1 simplification)**.
- Revoked refresh token: `TokenRevokedError`.
- Expired refresh token: `TokenExpiredError`.

**`LogoutHandler`**
- Valid refresh token: revoked, audit `logout`/success.
- Already-revoked or unknown token: idempotent success, no error.

**`RequestPasswordResetHandler`**
- Existing active user: reset token generated, `PasswordResetRequested` published with reference id only, no raw secret.
- Unknown email: response identical in shape to the success case; **no** token created and **no** event published (explicit no-side-effect assertion).
- Rate limit exceeded: rejected before token generation.

**`ConfirmPasswordResetHandler`**
- Valid, unused, unexpired token + password meeting strength policy: password updated, token marked used, **all** existing refresh tokens for that user revoked, audit `password_change`/success.
- Expired / used / unknown token: rejected, audit failure.
- Weak new password: rejected before touching the repository.

**Internal reveal endpoint handler** (consumed by `notification-service`)
- Valid, not-yet-revealed reference id: returns the raw secret once, marks it revealed.
- Second reveal attempt on the same reference id: rejected (replay defense).
- Expired reference id: rejected.
- Caller without valid internal service credentials: rejected; every reveal attempt (success or not) writes an audit record.

## 2. Integration test cases (testcontainers: Postgres, Redis, RabbitMQ)

- `PostgresUserRepository`: save→get round-trip; case-insensitive `get_by_email`; DB-level unique constraint on email surfaces as a domain-level exception, not a raw DB error.
- `PostgresTokenRepository`: save→get round-trip for all three token kinds; expired tokens remain readable (not silently deleted); `revoke()` persists and is immediately reflected.
- Outbox: event append + outbox row insert are atomic (simulated failure between them leaves neither); relay worker publishes pending rows and doesn't republish already-published ones; a simulated crash mid-relay doesn't lose the event.
- `PostgresAuditRepository`: the DB role backing this table can `INSERT` but not `UPDATE`/`DELETE` (asserted against the real DB role); every auditable action produces a record on both outcomes.
- `Argon2PasswordHasher`: hash→verify round-trip; wrong password rejected; two hashes of the same plaintext differ (salt) but both verify.
- `JwtTokenIssuer`: issued token verifies against the service's own published public key; claims are exactly `user_id` + `roles`; tampered payload fails verification; expired token fails verification; JWKS response is valid JWK Set JSON containing only public key material.
- `RedisRateLimiter`: allows under threshold, rejects at/over threshold, resets after the window; **Redis connection failure surfaces a typed exception that the application layer maps to a 503 (fail-closed)**.
- `RabbitMqEventPublisher`: publishes to the correct exchange/routing key per `messaging-conventions` naming, consumable by a test subscriber.

## 3. Contract test cases

**HTTP**, happy path + error path against the OpenAPI schema, for every endpoint: `register`, `verify-email`, `login`, `refresh`, `logout`, `password-reset/request`, `password-reset/confirm`, `GET /.well-known/jwks.json`, and the internal `reveal` endpoint. Notable cross-cutting assertions:
- `login` failure responses are byte-identical in shape across wrong-password / unknown-email / unverified / locked.
- `password-reset/request` always responds `202` with the same body, regardless of whether the email exists.
- No response body, on any endpoint, ever contains `password_hash` or a raw token outside its one intended field.
- `reveal` is asserted absent from the public API catalog surface (internal-only, never routed through Kong).

**Event schema contracts** (`docs/events-catalog.md`):
- `UserRegistered` (v1) — includes the new `email_verification_token_reference_id` field; `architecture-agent` confirmation it doesn't break existing consumers (`profile-service`, `diary-service`).
- `PasswordResetRequested` (v1, new) — `user_id`, `email`, `reset_token_reference_id`, `requested_at`, no raw secret.
- `NewDeviceLoginDetected` (v1, new) — `user_id`, `device_fingerprint_hash`, `occurred_at`, no raw credentials.
- Idempotent-consumption tests for these three events are the *consumer's* obligation (`notification-service`, `profile-service`, `diary-service`), not identity-service's.

## 4. E2E test cases

**None for this change.** Journey 1 in `docs/testing-strategy.md` §2.4
("Register → log a food item → see totals") needs `catalog-service`,
`diary-service`, and `nutrition-calculation-service`, none of which exist
yet. The register+login flow built here will be reused as a fixture once
those services exist.

## 5. Event-sourcing-specific cases

**N/A.** `identity-service` is not `diary-service` or
`nutrition-calculation-service` (ADR-0002).

## 6. Coverage expectation

- **Domain ≥ 90%** — every state transition (registration, verification, lock/unlock, password change, token expiry/single-use, device recognition) is covered above.
- **Application ≥ 85%** — all 8 handlers have happy-path + every documented failure branch covered.
- **Infrastructure ≥ 70%** — every adapter's round-trip and failure-surfacing behavior is covered. Actual % confirmed by `pytest-cov` at `/test-execution`.

**Infra (Terraform/K8s) validation gate**, from `/plans/platform-infra/implementation-plan.md` §8: `terraform fmt -check` + `validate` clean, `tflint`/`checkov`/`tfsec` clean or justified, `terraform plan` output reviewed before any apply, `helm lint` + `helm template` render against a synthetic values file for the `_lib` chart.
