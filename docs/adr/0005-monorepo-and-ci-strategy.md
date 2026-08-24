# ADR-0005: Monorepo with per-service CI pipelines

## Status
Accepted

## Date
2026-08-23

## Context
NutriApp is built from day one as multiple independently deployable
microservices (see ADR-0003), but by a single contributor (human + AI agents),
not a multi-team organization. Splitting into per-service repositories from
the start would add coordination overhead (cross-repo PRs for any change that
touches an event contract, duplicated tooling config, harder atomic commits
across a domain change) without the benefit it exists for (independent teams
needing independent release cadences and access control).

## Decision
A single repository (monorepo) holds all services, the frontend, all
`.claude/` agent/skill definitions, all documentation, and all infrastructure
code (Terraform, Kubernetes manifests). CI/CD pipelines run **per service**,
not as one monolithic pipeline, using path-based filtering so a change to
`diary-service/` only triggers `diary-service`'s pipeline (plus contract
tests for any service that consumes its events).

Repository layout:
```
nutriapp/
  services/
    identity-service/
    catalog-service/
    diary-service/
    nutrition-calculation-service/
    food-recognition-service/
    analytics-service/
    nutrition-assistant-service/
  frontend/
  packages/
    shared-contracts/     # shared event/DTO types, versioned independently
  infra/
    terraform/
    k8s/
  .github/workflows/
  .claude/
  docs/
```

## Considered Alternatives
- **Repo per service** — mirrors true microservice team autonomy, but for a
  solo/AI-agent-driven project it multiplies context-switching cost and makes
  cross-service event contract changes require coordinated multi-repo PRs.
  Rejected for now; revisit if the team grows.
- **True monolith, single deployable** — simplest CI, but contradicts the
  explicit requirement to model independent bounded contexts and independent
  deploy pipelines from the start (ADR-0003). Rejected.

## Consequences
### Positive
- Atomic commits across a domain change (e.g. new event + producer + consumer)
  in one PR.
- Shared tooling config (linters, pre-commit, CI templates) lives once.
- `packages/shared-contracts` gives a single source of truth for cross-service
  types without a package registry.

### Negative / Trade-offs
- CI must be carefully path-filtered or every commit re-tests everything.
- A single repo means a single point of git history size growth; large binary
  assets (fixture images for `food-recognition-service`) should use Git LFS if they grow.
- IAM/CI permissions must still be scoped per service even though the code
  lives together (a compromised `catalog-service` pipeline should not be able
  to deploy `identity-service`).

### Follow-up actions
- Implement path-filtered GitHub Actions workflows (`docs/ci-cd-strategy.md`).
- Define `CODEOWNERS` per service directory even in a solo project, as a
  forcing function for the human-in-the-loop review gate.

## References
- ADR-0003 (microservices per domain)
- `docs/ci-cd-strategy.md`
