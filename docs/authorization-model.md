# Authorization Model (RBAC/ABAC)

Expands `docs/security-and-compliance.md` section 1 (Authentication) with
the authorization side: once we know *who* the request is from, what are
they allowed to do. Owned by `identity-service`, enforced by every service
that receives its tokens.

## 1. Model Choice

**Default: Role-Based Access Control (RBAC) with resource-scoped roles**,
escalating to Attribute-Based Access Control (ABAC) only for specific
rules that don't fit a role cleanly.

- A **role** (e.g. `owner`, `admin`, `member`, `viewer` — rename to your
  domain's actual roles) grants a fixed set of permissions.
- If ADR-0018 selects multi-tenancy (Option B or C), roles are scoped
  **per tenant/organization** — a user can hold different roles in
  different organizations, never a single global role.
- Escalate a specific permission to ABAC (a rule evaluated against
  request attributes, not just role membership) only when a role can't
  express it cleanly — e.g. "a user can edit their own record but not
  others'" is an attribute check (`resource.owner_id == subject.user_id`),
  not a role. Don't build a general-purpose policy engine (OPA/Cedar)
  until more than a handful of such rules exist — a hardcoded check in
  the domain layer is fine for the first few.

## 2. Token Contents & Propagation

- **Signing mechanism and JWKS distribution are specified in full in
  `docs/adr/0022-token-signing-and-jwks.md`** — this section covers claim
  content and propagation only. Summary: RS256 asymmetric signing, a
  short-lived access token (not individually revocable) plus a
  server-side-tracked, individually revocable refresh token, public key
  published via a JWKS endpoint so every service verifies locally.
- JWT access token (per `docs/security-and-compliance.md` section 1,
  ADR-0022) carries: `user_id`, `roles` (per-tenant if multi-tenant), and
  a short expiry (15 min default, tunable).
- **Permissions are never embedded in the token directly** — only roles.
  A permission-to-role mapping can change (a role gains a new permission)
  without invalidating every already-issued token; embedding raw
  permissions would require a full token refresh on every policy change.
- Every internal service-to-service call propagates the original
  `user_id`/roles via the same correlation metadata used for tracing
  (CLAUDE.md section 2.8) — a downstream service never re-derives
  "who is this request for" from anything other than the validated token
  claims forwarded by `bff-service`/Kong.

## 3. Enforcement Point

- **Kong** (CLAUDE.md section 2.2) validates the JWT signature and
  expiry at the edge — this is authentication, not authorization.
- **Coarse-grained authorization** (does this role have any access to
  this endpoint at all) can be enforced at Kong via a plugin, as
  configuration, not code.
- **Fine-grained authorization** (does this specific user have access to
  this specific resource instance) is **always enforced in the owning
  domain service's application layer**, never left to the frontend or to
  Kong — CLAUDE.md section 2.2 already states `bff-service` "contains
  orchestration only, never business logic," and authorization decisions
  about a specific resource are business logic.
- Every query and command handler that operates on a specific resource
  instance must include an authorization check as an explicit step, not
  an assumption that "the user could only have gotten this ID if they
  had access" — object reference IDs are not a security boundary
  (guards against IDOR — Insecure Direct Object Reference).

## 4. Testing Requirements

- Every authenticated endpoint has at least one test asserting a
  request with insufficient permissions is rejected (403), not just that
  a request with sufficient permissions succeeds.
- If multi-tenant (ADR-0018 Option B/C): every tenant-scoped endpoint has
  an explicit cross-tenant test (user from tenant A attempts to access
  tenant B's resource, expected to fail) — this is release-blocking per
  `docs/testing-strategy.md`, not optional coverage.
- Role-to-permission mapping changes are covered by a test asserting the
  new mapping, and a regression test confirming no other role gained an
  unintended permission as a side effect.

## 5. Auditability

- Every authorization decision that **denies** access to a sensitive
  resource is logged to the audit trail (`docs/observability-and-audit.md`)
  with the requesting user, the resource, and the missing
  permission/role — this is what makes an unauthorized-access attempt
  investigable after the fact.
- Role assignment/revocation itself is an audited action (who granted
  what role to whom, when) — treated with the same immutability
  requirement as other audit records.

## 6. Ownership

`identity-agent` owns the role/permission data model and token issuance.
`security-agent` reviews any change to the permission-to-role mapping or
any new authorization check pattern. Every other domain agent is
responsible for actually calling the authorization check in its own
service — `identity-service` provides the model, it does not enforce
authorization on another service's behalf.
