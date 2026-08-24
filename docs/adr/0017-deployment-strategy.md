# ADR-0017: Deployment Strategy (Rolling -> Canary/Blue-Green Activation)

## Status
Accepted

## Date
2026-08-23

## Context
`docs/containerization-and-orchestration.md` specifies a **rolling update**
(`maxSurge: 1`) as the default Kubernetes deployment strategy, with
canary/blue-green explicitly deferred as a "follow-up once needed." Left
unresolved, that deferral tends to become permanent by default rather than
a decision revisited on evidence — this ADR closes that gap by making the
activation condition explicit, the same pattern already used for ADR-0012
(catalog search) and ADR-0004 (Kafka fallback).

## Decision
- **Start with rolling update** for every service (CLAUDE.md section 2.9,
  `docs/containerization-and-orchestration.md`): zero new tooling, native
  to Kubernetes, sufficient for low-traffic/early-stage services where a
  bad rollout affects a small blast radius and is caught quickly by
  health checks + `PodDisruptionBudget`.
- **Activation condition for canary deployments** — revisit via a new ADR
  once *any* of the following is true for a given service, not assumed
  for all services simultaneously:
  - The service has a measured SLO (`docs/observability-slo.md`) with an
    error budget tight enough that a bad rolling-update batch could
    plausibly burn a meaningful fraction of it before automated rollback
    triggers.
  - The service is on the critical path identified in
    `docs/performance-testing.md`'s hot-path table, and a regression
    would be user-visible before the next full rollout completes.
  - The team (human + agents) has been burned at least once by a rolling
    update that partially degraded production before manual rollback —
    i.e. activate reactively on real incident evidence, not
    speculatively.
- **When activated**, prefer **Argo Rollouts** (Kubernetes-native,
  integrates with the existing Helm-based deployment model in
  `docs/containerization-and-orchestration.md`, open-source) over a
  managed alternative, consistent with this project's general bias
  toward open/self-hostable tooling (see `docs/mcp-servers.md`).
  Canary analysis gates on the same Prometheus SLIs already defined in
  `docs/observability-slo.md` — no new metrics pipeline required.
- **Blue-green** is the fallback choice specifically for
  `diary-service`-class services using full event sourcing (ADR-0002),
  where a canary's partial-traffic window is harder to reason about
  against an event stream than an atomic cutover — document the specific
  choice per service in that service's own `README.md` once activated.
- Database migrations remain governed by the expand/contract pattern in
  CLAUDE.md section 2.5 regardless of deployment strategy — canary/blue-green
  changes *traffic* routing, not the zero-downtime migration discipline.

## Considered Alternatives
- **Canary/blue-green from day one for every service** — better safety
  net, but real operational cost (a progressive-delivery controller to
  run, observe, and debug) before there is traffic or team size to
  justify it. Rejected for the same reason ADR-0012 rejects a dedicated
  search engine ahead of measured need.
- **Feature-flag-based progressive rollout only (no traffic-level
  canary)** — cheaper (reuses `docs/feature-flags.md`'s Unleash setup),
  but only protects flagged code paths, not infrastructure-level
  regressions (a bad container image, a broken health check). Kept as a
  complementary technique, not a substitute — flags and canary
  deployments solve different problems and are used together once
  canary is activated.

## Consequences
### Positive
- No new infrastructure until a concrete, measured trigger justifies it.
- The eventual migration to canary is a planned, ADR-documented event,
  not an ad-hoc reaction mid-incident.

### Negative / Trade-offs
- Until activated, a bad rolling-update batch is caught by health
  checks/`PodDisruptionBudget` and rollback, not prevented by
  progressive traffic shifting — acceptable at current scale, revisit
  per the trigger above.

### Follow-up actions
- Add deployment-strategy status (rolling vs canary vs blue-green) as a
  field in each service's `README.md` once scaffolded.
- Track canary-activation trigger evaluation as part of the quarterly SLO
  review already defined in `docs/observability-slo.md` section 6.

## References
- `docs/containerization-and-orchestration.md`
- `docs/observability-slo.md`
- `docs/performance-testing.md`
- ADR-0002, ADR-0012
