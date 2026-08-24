# Project Status

Summary index of actual implementation state, per
`docs/project-status-tracking.md`. Updated as part of `/create-pr` when a
merged change moves a service from one status to another. This is a
summary, not a changelog — see git history and `docs/adr/` for detail.

## Services

| Service | Scaffolded? | Core domain implemented? | Deployed to dev? | Deployed to staging/prod? | Last significant change |
|---|---|---|---|---|---|
| `identity-service` | Yes | Yes — 139 tests passing (domain 99%, application 98%, infrastructure 91% coverage) | No — Terraform written and `plan`-validated, `apply` not yet run | No | 2026-08-24 — PR #1 merged: full hexagonal implementation (registration, login, tokens per ADR-0022, password reset, RBAC), reference for every other service |
| `profile-service` | No | No | No | No | — |
| `catalog-service` | No | No | No | No | — |
| `diary-service` | No | No | No | No | — |
| `nutrition-calculation-service` | No | No | No | No | — |
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

All 22 ADRs are **Accepted** (0001–0022). None Proposed or Superseded.
Most recent: ADR-0022 (Token Signing Scheme and JWKS Distribution),
accepted 2026-08-24 alongside `identity-service`'s merge.
