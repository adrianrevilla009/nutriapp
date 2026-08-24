---
description: Monorepo workspace and dependency-boundary conventions for NutriApp. Use whenever adding a new package/service, adding a cross-service dependency, or touching root-level build tooling (Makefile, workspace config).
---

# Monorepo Tooling Conventions — NutriApp

Full policy: `docs/monorepo-tooling.md`. Rationale: ADR-0005.

## Rules
- Python services: independent `pyproject.toml`/lockfile per service (uv
  workspaces) — do not force all services onto one shared dependency set.
- Frontend: pnpm workspaces.
- A service NEVER imports another service's internal code directly — only
  through its published HTTP API or its events. The only shared code is
  `packages/shared-contracts` (data shapes only, no business logic).
- A change to `packages/shared-contracts` triggers contract tests for every
  consuming service, not just the one that changed it.
- New root-level tooling (Makefile targets, CI path filters) is documented in
  the root `README.md` immediately, not left for someone to discover.
