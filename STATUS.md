# Project Status

Summary index of actual implementation state, per
`docs/project-status-tracking.md`. Updated as part of `/create-pr` when a
merged change moves a service from one status to another. This is a
summary, not a changelog — see git history and `docs/adr/` for detail.

## Services

| Service | Scaffolded? | Core domain implemented? | Deployed to dev? | Deployed to staging/prod? | Last significant change |
|---|---|---|---|---|---|
| `identity-service` | Yes | Yes — 139 tests passing (domain 99%, application 98%, infrastructure 91% coverage) | No — Terraform written and `plan`-validated, `apply` not yet run | No | 2026-08-24 — PR #1 merged: full hexagonal implementation (registration, login, tokens per ADR-0022, password reset, RBAC), reference for every other service |
| `profile-service` | Yes | Yes — 183 tests passing (domain 99%, application 98%, infrastructure 84% coverage) | No — Terraform written (`profile-service.tf`, mirrors `identity-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-27 — PR #5 merged: internal `POST /internal/v1/profile/{user_id}/reveal-metrics` endpoint for `nutrition-calculation-service` to consume biometric/goal data cross-service, served on a dedicated internal-only ASGI app/port never routed through Kong (implementation plan Addendum 2), per-caller credential + rate limiting + audit trail + exactly-6-field response minimization. Builds on PR #2's 2026-08-25 CQRS/event-sourced base (ProfileCreated, BiometricConsentGranted, WeightRecorded, BodyMetricRecorded, GoalSet, GoalUpdated) and its AES-256-GCM per-user encryption via its own KMS key per ADR-0023 |
| `catalog-service` | Yes | Yes — 97 tests passing (domain 97%, application 97%, infrastructure 89% coverage) | No — Terraform written (`catalog-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-26 — PR #4 merged: conventional-persistence/event-driven-CRUD implementation, multi-source pluggable ingestion (`CatalogSourcePort`: Open Food Facts bulk export + USDA FoodData Central API), barcode-based dedup/merge, Postgres full-text/`pg_trgm` search per ADR-0012. No adapter for Mercadona/Carrefour/Dia/Alcampo/Eroski — no official API, ToS prohibits reproduction, documented per `external-data-ethics` SKILL.md. Zero live external HTTP calls anywhere in the shipped code/tests (verified at `/implementation-review`) |
| `diary-service` | Yes | Yes — 147 tests passing (domain 97%, application 100%, infrastructure 87% coverage) | No — Terraform written (`diary-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-26 — PR #3 merged: full CQRS/event-sourced implementation, second ES/CQRS service after `profile-service` with a freshly-justified async-projector-via-broker choice (higher write volume) and mixed aggregate granularity (per-item for Food/Water/Meal-Plan entries, per-user for Fasting Window, to enforce the no-overlap invariant atomically). 10 domain events |
| `nutrition-calculation-service` | Yes | Yes — 139 tests passing (domain 98%, application 100%, infrastructure 94% coverage) | No — Terraform written (`nutrition-calculation-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-27 — PR #6 open (CI green, awaiting human merge): event-driven-CRUD implementation per ADR-0002's explicit non-event-sourced "computed value" service, macro/micro totals from `diary-service`/`catalog-service` events, Mifflin-St Jeor goal-setting engine consuming `profile-service`'s biometric/goal data via the new reveal-metrics endpoint (PR #5) |
| `food-recognition-service` | No | No | No | No | — |
| `notification-service` | No | No | No | No | — |
| `bff-service` | No | No | No | No | — |
| `activity-service` | No | No | No | No | — |
| `recipe-service` | No | No | No | No | — |
| `social-service` | No | No | No | No | — |
| `billing-service` | No | No | No | No | — |
| `analytics-service` | No | No | No | No | — |
| `nutrition-assistant-service` | No | No | No | No | — |

## Cross-Cutting

### Terraform modules

All modules below exist as code and pass `fmt`/`validate`/`tflint`/
`checkov` (275 passed, 0 failed) and a combined `terraform plan` (84 to
add, 0 to change, 0 to destroy). **None have been `apply`'d to any
environment** — that is a human-only action per CLAUDE.md §7, not yet
taken.

| Module | Exists (code) | Applied to `dev` | Applied to `staging`/`prod` |
|---|---|---|---|
| `bootstrap` (remote state) | Yes | No | No |
| `vpc` | Yes | No | No |
| `eks` | Yes | No | No |
| `rds` | Yes | No | No |
| `elasticache` | Yes | No | No |
| `secrets` | Yes | No | No |
| `scale-to-zero` | Yes | No | No |
| `ecr` | Yes | No | No |

### MCP servers

Per `docs/mcp-servers.md`: all entries remain disabled. None connected in
this project to date.

### ADRs

All 23 ADRs are **Accepted** (0001–0023). None Proposed or Superseded.
Most recent: ADR-0023 (Per-Service Ownership of Erasable-Data Encryption
Keys), accepted 2026-08-25 alongside `profile-service`'s merge.
