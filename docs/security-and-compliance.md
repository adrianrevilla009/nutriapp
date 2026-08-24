# Security and Compliance

See also `docs/authorization-model.md` (RBAC/ABAC, expanding on the
"Authorization" half of section 1 below), `docs/compliance-mapping.md`
(mapping every practice in this document to a formal framework's control
list, per ADR-0020), and `docs/vendor-risk-register.md` (tracking the DPA
status of every third-party processor mentioned in sections 3 and 4).

## 1. Authentication & Authorization
- Password hashing via `argon2` (preferred) or `bcrypt`. Never a custom scheme.
- Session/authorization tokens: JWT (short-lived access token + refresh token),
  signed with an asymmetric key pair so other services can verify tokens without
  holding the signing secret.
- **Authorization (roles, permissions, tenant scoping) is specified in full
  in `docs/authorization-model.md`** — this section covers authentication only.
- Rate limiting on all authentication endpoints (login, password reset,
  registration) to mitigate brute-force and enumeration attacks.
- Principle of least privilege: each service's database role has only the
  permissions it needs (no service account has superuser/admin rights).

## 2. Secrets Management
- No secrets committed to git, ever, including in `.env` files (`.env` is
  gitignored; only `.env.example` with placeholder values is committed).
- Local development secrets live in `.env` (gitignored); production secrets are
  managed via the deployment platform's secret store, never hardcoded in
  `docker-compose.yml` or Dockerfiles.
- Rotate any secret that was ever accidentally committed, immediately, even
  after removing it from history.
- Full mechanism (AWS Secrets Manager + External Secrets Operator, IRSA
  scoping, rotation runbooks): see `docs/secrets-management.md` and ADR-0007.

## 3. Personal Data Handling
- Any sensitive personal data your domain handles (see `docs/data-protection-and-privacy.md` section 0) is treated accordingly.
  Minimize retention to what the product needs; support data export and
  account/data deletion as first-class features, not afterthoughts.
- Media uploaded for recognition (if the product has `food-recognition-service`) is processed and may be
  discarded after extraction unless the user explicitly opts in to
  keeping it.
- Third-party scraping never collects personal data of third parties — see
  `.claude/skills/external-data-ethics/SKILL.md`.
- Full treatment (legal basis, consent, third-party AI data transmission,
  right-to-erasure via crypto-shredding, retention defaults, DSAR handling):
  see `docs/data-protection-and-privacy.md`.

## 4. Input Validation & Injection Prevention
- All external input validated at the boundary via Pydantic schemas before it
  reaches application/domain code.
- Parameterized queries only (SQLAlchemy ORM/Core) — no raw string-interpolated
  SQL.
- File uploads (any user-submitted media) validated for type/size before processing; never
  executed or interpreted as code.

## 5. Dependency & Supply Chain Security
- Dependency vulnerability scanning (`pip-audit` or equivalent) as part of CI.
- Pin dependency versions; review and test before bumping major versions.

## 6. Threat Modeling (lightweight, per service)
When `security-agent` reviews a new service or a significant change, it
considers, at minimum:
- What data does this service hold, and what is the impact if it is exposed?
- What is the trust boundary with adjacent services and with the frontend?
- Can an attacker replay a message, forge a token, or bypass a circuit breaker
  to cause resource exhaustion?

## 7. Guardrail Cross-Reference
See CLAUDE.md section 7 for the full list of actions that require explicit
human confirmation before execution (destructive migrations, `terraform
apply`/`destroy`, bulk scraping, user data deletion, hook/permission changes).

## 8. Related Documents
- `docs/secrets-management.md` — full secrets lifecycle (ADR-0007).
- `docs/data-protection-and-privacy.md` — full data protection posture,
  consent, and erasure mechanics.
- `docs/observability-and-audit.md` — audit trail mechanics.
- `docs/api-standards.md` — rate limiting enforced at the Kong gateway.
