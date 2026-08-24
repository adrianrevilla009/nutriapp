# ADR-0022: Token Signing Scheme and JWKS Distribution

## Status
Accepted — `architecture-agent` confirmed the `identity-service` implementation matches this decision exactly (RS256, access-token claims, refresh-token revocation model) during `/implementation-review` on 2026-08-24; `docs/authorization-model.md` §2 now references this ADR, closing the follow-up action below.

## Date
2026-08-24

## Context
`identity-service` is about to be implemented as NutriApp's reference
service (CLAUDE.md section 14). It must issue tokens that every other
service can verify, and — per `docs/domain-glossary-and-context-map.md` —
`identity-service` relates to every other bounded context as a **Shared
Kernel** (the `user_id` identity concept) exposed via an **Open Host
Service**: other services verify JWT claims validated at Kong, not by
calling `identity-service` synchronously per request. That relationship
requires other services to verify a token's signature *locally*, without a
network round trip to `identity-service` on every request — which in turn
requires an asymmetric signing scheme, not a shared symmetric secret.

This is the first time NutriApp defines this scheme — there is no prior
token contract to preserve compatibility with. `.claude/agents/identity-agent.md`
already flags "any change to the token signing scheme or session model" as
significant enough to warrant an ADR; this ADR treats the *initial*
definition of that scheme with the same rigor, since every future service's
auth integration will be built against whatever is decided here.

Forces at play:
- **Verification without coupling**: `bff-service`, Kong, and every domain
  service need to validate a token's signature and read its claims (`user_id`,
  `roles`) without depending on `identity-service`'s uptime for every
  request (CLAUDE.md section 2.6 — no unbounded synchronous dependency
  chains).
- **Revocation vs. statelessness**: JWTs are stateless by design, which
  conflicts with the ability to revoke a session immediately (e.g. on
  logout, or a detected compromise).
- **Scope discipline**: `docs/authorization-model.md` already mandates that
  tokens carry roles only, never raw permissions, and that fine-grained,
  per-resource authorization stays in the owning domain service, not in the
  token. This ADR only needs to decide the *transport and revocation*
  mechanics, not re-litigate the authorization model.
- NutriApp is single-tenant B2C (ADR-0018, Accepted) — no per-tenant role
  scoping is needed in the token.

## Decision
`identity-service` issues two token types, both JWT, signed with an
**asymmetric key pair (RS256)**:

- **Access token**: short-lived (15 minutes default, tunable), carries
  `user_id` and `roles` claims only. **Not individually revocable** — a
  compromised access token is bounded by its own short expiry rather than
  requiring a revocation check on every request.
- **Refresh token**: longer-lived, opaque to other services (not a JWT
  verified by anyone but `identity-service` itself), **stored server-side
  in Postgres and individually revocable** (logout, detected compromise,
  password change all revoke it). Refresh is the only mechanism for
  obtaining a new access token.

`identity-service`'s public key is published via a **JWKS endpoint**
(`/.well-known/jwks.json`, per the RFC 7517 convention), which every other
service fetches (and caches, with routine key rotation in mind) to verify
access tokens locally — no synchronous call to `identity-service` is made
to validate a request's token.

**Roles for v1: `USER` and `ADMIN` only.** No per-tenant role scoping
(consistent with ADR-0018). Escalation to attribute-based checks for
resource-level ownership stays in each owning service's application layer,
per `docs/authorization-model.md` section 1 — this ADR does not introduce
any new authorization primitive beyond these two roles.

## Considered Alternatives
- **Symmetric signing (HS256) with a shared secret distributed to every
  service** — simpler key management (one secret, no JWKS endpoint to
  build), but every service that can *verify* a token can also *forge*
  one, since the same secret does both. This violates the principle that
  only `identity-service` should be able to mint valid tokens. Rejected.
- **Revocable access tokens via a shared revocation-check cache (Redis) on
  every request** — would allow immediate access-token revocation, but
  reintroduces a synchronous dependency (a Redis lookup) into every
  authenticated request across every service, which is exactly the
  coupling the Open Host Service pattern is meant to avoid, and adds a
  new single point of failure system-wide. Rejected in favor of
  short-lived access tokens + revocable refresh tokens, which bounds the
  blast radius of a compromised access token to its expiry window without
  a per-request dependency.
- **Opaque access tokens verified via a synchronous call to
  `identity-service` on every request** — maximizes revocation precision,
  but directly contradicts the Open Host Service relationship already
  decided in `docs/domain-glossary-and-context-map.md` and would make
  `identity-service` a hard synchronous dependency for every request in
  the system. Rejected.

## Consequences
### Positive
- Every service can verify tokens locally, keeping `identity-service` out
  of the synchronous request path for the rest of the system.
- Only `identity-service` holds the private signing key — no other
  service can forge a valid token.
- Revocation is still meaningfully possible (logout, compromise, password
  change) via the refresh token, without paying a per-request cost.

### Negative / Trade-offs
- A compromised access token remains valid until its expiry (up to 15
  minutes) even after the corresponding refresh token is revoked — this
  is an explicit, bounded risk accepted in exchange for not coupling every
  request to a revocation check.
- Key rotation requires every consuming service to refresh its cached
  JWKS response; consumers must not cache the JWKS response indefinitely
  (a rotation grace period / max-age needs to be respected, not just a
  one-time fetch at service startup).
- Two different persistence/verification models for two token types
  (stateless JWT vs. server-side-tracked refresh token) — must be
  documented clearly in `identity-service`'s own `README.md` so this
  asymmetry doesn't get "simplified" away by a future contributor.

### Follow-up actions
- `identity-service`'s implementation plan (in progress) implements the
  `TokenIssuerPort` / `JwtTokenIssuer` adapter and the JWKS endpoint per
  this decision.
- Document the JWKS consumption pattern (fetch + cache + rotation
  handling) as guidance for every future service that verifies these
  tokens — candidate addition to `.claude/skills/resilience-patterns/SKILL.md`
  or a new shared snippet in `packages/shared-contracts`, to avoid each
  service reimplementing JWKS-fetch-and-cache logic independently.
- Update `docs/authorization-model.md` section 2 ("Token Contents &
  Propagation") to reference this ADR as the authoritative source for the
  signing mechanism, rather than only describing claim contents.
- `architecture-agent` review requested for consistency with
  `docs/domain-glossary-and-context-map.md`'s Open Host Service
  classification before this ADR is marked Accepted.

## References
- CLAUDE.md, section 2.2 (service communication) and section 2.6
  (resilience — no unbounded synchronous dependency)
- `docs/authorization-model.md` (role/claim content, enforcement points)
- `docs/domain-glossary-and-context-map.md` (`identity-service` as Shared
  Kernel / Open Host Service)
- ADR-0018 (single-tenant, B2C — no per-tenant role scoping)
- `.claude/agents/identity-agent.md` (token signing scheme changes require
  an ADR)
