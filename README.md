# NutriApp

NutriApp lets users register, browse and search a product inventory
scraped from supermarket APIs, log what they eat — including water intake,
fasting windows, and planned meals — against that inventory or against
AI-recognized food photos and barcode scans, see computed macro and
micronutrient breakdowns, track biometric evolution over time with
auto-calculated goals, log exercise and sync wearables, and, on a paid Pro
plan, share/export data, generate reports, connect with other users, and
publish/discover recipes.

Planned as a monorepo of hexagonal microservices, to be developed by a
human + Claude Code agents under a strict human-in-the-loop workflow.

**Start here: [`CLAUDE.md`](./CLAUDE.md)** — the single source of truth for
architecture, engineering standards, and the agent operating model. Every
other document in this repo exists to support or expand on it.
[`DOMAIN-SETUP.md`](./DOMAIN-SETUP.md) documents the domain-instantiation
checklist this repo was already run through, and remains useful reference
if this template is ever reused for a sibling project.

## Current State

**Specification phase only.** This repository currently contains no
application code and no infrastructure code — only the complete
architectural, operational, and process specification that will guide
implementation: `CLAUDE.md`, the ADRs, the full `docs/` set, and the Claude
Code agent/skill/command definitions under `.claude/`.

Terraform, Kubernetes manifests, CI/CD pipelines, `docker-compose.yml`, and
all application services are **not yet written**. They will be produced
later, incrementally, by Claude Code agents following the human-in-the-loop
pipeline in `CLAUDE.md` section 6 — starting with `identity-service` as the
reference implementation (see `CLAUDE.md` section 14).

## Map of the Repository

| Path                    | What lives here                                                                  |
|--------------------------|-----------------------------------------------------------------------------------|
| `DOMAIN-SETUP.md`          | Checklist to instantiate this template for a new product/domain — read this first  |
| `CLAUDE.md`                | Architecture, standards, and agent operating model                                  |
| `ARCHITECTURE.md`           | High-level diagrams                                                                    |
| `docs/`                       | Full specification behind every summary in `CLAUDE.md`                                   |
| `docs/adr/`                      | Architecture Decision Records                                                              |
| `.claude/agents/`                  | Claude Code subagent definitions, one per domain + cross-cutting concerns                    |
| `.claude/skills/`                     | Convention references agents load for specific kinds of work                                   |
| `.claude/commands/`                      | Slash commands implementing the human-in-the-loop pipeline (`/implementation-plan`, `/test-plan`, etc.) |
| `.claude/hooks/`                            | Guardrails that technically block destructive actions without human confirmation                  |
| `docs/ai-agent-governance.md`                  | Decision-authority boundaries for development-time agents and product-time AI features                  |
| `docs/project-status-tracking.md`                | Spec for how real implementation state is tracked once implementation begins (`/project-status`)          |
| `docs/supply-chain-security.md`                  | SAST, SBOM, and proactive dependency updates (ADR-0009)                                                    |
| `docs/edge-and-cdn.md`                           | CloudFront + WAF at the edge, in front of the API gateway (ADR-0010)                                       |
| `docs/notifications.md`                          | `notification-service`: transactional email and push delivery (ADR-0011)                                   |
| `docs/chaos-engineering.md`                      | Chaos experiments against `staging` to verify resilience patterns hold under real failure (ADR-0016)        |
| `docs/authorization-model.md`                    | RBAC/ABAC model, token scoping, enforcement boundaries                                                     |
| `docs/multi-tenancy.md`                          | Confirms single-tenant, B2C scope (ADR-0018, Accepted) — no tenant isolation model needed                    |
| `docs/sagas-and-distributed-transactions.md`     | Catalog of cross-service business transactions and compensations (ADR-0019)                                 |
| `docs/compliance-mapping.md`                     | GDPR baseline control-to-evidence mapping (ADR-0020, Accepted)                                                |
| `docs/product-requirements.md`                   | Full feature list, bounded-context ownership, and Phase 1/Phase 2 scope                                       |
| `docs/domain-glossary-and-context-map.md`        | Shared vocabulary and bounded-context relationships (DDD)                                                    |
| `docs/code-quality.md`                           | Static code quality gates (SonarQube) complementing test coverage                                            |
| `docs/data-platform-and-analytics.md`            | Domain analytics vs. product analytics vs. future data warehouse/BI                                          |
| `docs/sla-and-contracts.md`                      | External commitments to customers, kept distinct from internal SLOs                                          |
| `docs/vendor-risk-register.md`                   | Every third-party processor, DPA status, and compliance relevance                                            |
| `docs/disaster-recovery-runbook.md`              | Actual restore procedure and quarterly drill cadence                                                         |
| `docs/multi-region-strategy.md`                  | Current single-region scope and the triggers that would change it                                            |
| `docs/onboarding.md`                             | Practical first-hour runbook for a new contributor or fresh agent session                                     |
| `.github/CODEOWNERS`, `.github/dependabot.yml`   | Review ownership and proactive dependency updates                                                          |

## Product Decisions (Resolved)

The four business decisions that block-instantiating a fresh copy of this
template needs are resolved, and their ADRs are **Accepted**:
- **ADR-0014** — mobile app strategy: responsive, PWA-capable web (Next.js)
  first; a native app is an explicit future option, not committed now.
- **ADR-0015** — billing and monetization: freemium with a paid Pro tier
  gating data export, reports, social features, and recipe
  publishing/search.
- **ADR-0018** — multi-tenancy strategy: single-tenant, B2C — one account
  per user, no organizations.
- **ADR-0020** — target compliance framework: GDPR baseline (biometric/
  health data in `profile-service` is Article 9 special-category data); no
  formal certification pursued yet.

Everything below this line does not exist yet — it is *specified* in
`docs/` and will be created by agents, following the plan/approve/implement
pipeline, not written directly:
- `services/` — microservices, once scaffolded
- `frontend/` — Next.js frontend, once scaffolded (spec: `docs/frontend-architecture.md`)
- `packages/shared-contracts/` — cross-service types (spec: `docs/monorepo-tooling.md`)
- `infra/terraform/` — AWS infrastructure as code (spec: `docs/terraform-and-infrastructure.md`)
- `infra/k8s/` — Helm charts for EKS (spec: `docs/containerization-and-orchestration.md`)
- `.github/workflows/` — CI/CD pipelines (spec: `docs/ci-cd-strategy.md`)
- `docker-compose.yml`, `.env.example`, `.pre-commit-config.yaml` — local dev tooling

## The Human-in-the-Loop Workflow

Every non-trivial change follows: spec -> implementation plan -> human
approval -> test plan -> human approval -> implementation -> test execution
-> implementation review -> test review -> human final approval -> commit ->
PR. See `CLAUDE.md` section 6 for the full pipeline and the slash commands
that implement each stage. This applies to infrastructure changes
(Terraform, Kubernetes) exactly as it applies to application code — no
agent generates or applies infrastructure outside this pipeline.
