# Monorepo Tooling

See ADR-0005 for why this is a monorepo at all. This document covers the
mechanics of working in it efficiently.

## 1. Workspace Manager

- **Python services**: managed as independent `uv` workspaces (or Poetry, if
  preferred, but pick one and stay consistent) — each service has its own
  `pyproject.toml` and lockfile, avoiding one giant shared dependency set
  that forces every service onto the same library versions unnecessarily.
- **Frontend**: `pnpm` workspaces (fast, disk-efficient via content-addressed
  storage — meaningful in a monorepo with many packages).
- **Cross-language build orchestration**: a `Makefile` or `Taskfile.yml` at
  the repo root providing consistent top-level commands (`make test`,
  `make lint`, `make up` for `docker-compose`) that delegate to each
  language's native tooling, so a contributor doesn't need to remember
  per-service invocation differences.

## 2. Shared Contracts Package

`packages/shared-contracts/` holds types that must stay identical across
service boundaries:
- Event payload schemas (JSON Schema, generated into both Python Pydantic
  models and TypeScript/Zod types via a codegen step, never hand-duplicated).
- Common DTOs used by more than one service's public API.

This package is versioned independently and consumed as a local path
dependency by every service — a schema change here is the trigger for
updating `docs/events-catalog.md` and running the full contract-test suite
across every consumer (`docs/testing-strategy.md` section 2.3).

## 3. Path-Based CI Filtering

CI (`docs/ci-cd-strategy.md`) uses `dorny/paths-filter` (or equivalent) to
determine which services' pipelines to run based on the diff. A change under
`packages/shared-contracts/` triggers **every** service's contract-test stage
(since any of them might depend on it), never just a subset.

## 4. Dependency Hygiene

- No service imports another service's internal code directly (only through
  its published API or its events) — enforced by import-linter/boundary
  checks in CI, not just code review discipline, since it's the one rule
  that would silently defeat the whole microservices boundary if violated.
- `packages/shared-contracts` is the only exception, and it contains data
  shapes only, never business logic.

## 5. Per-Service `CLAUDE.md`

The root `CLAUDE.md` is the single source of truth for architecture-wide
rules (CLAUDE.md itself, section headline). Once a service is scaffolded,
add a **service-local `CLAUDE.md`** at `services/<name>/CLAUDE.md`
containing only what's specific to that service and would otherwise force
every agent to re-derive it from reading code:
- The service's own bounded context boundary in one paragraph (agents
  working elsewhere in the monorepo should not need to load this file).
- Any service-specific exception to a general rule, always with a
  cross-reference to the general rule it deviates from and why (an
  undocumented exception is a bug, not a convention).
- Non-obvious local commands (`make test` inside that service directory, if
  it differs from the root `Makefile` target).

A service-local `CLAUDE.md` **never restates** anything already true
project-wide (hexagonal layout, testing thresholds, the human-in-the-loop
pipeline) — Claude Code reads both the root and the nearest service-local
`CLAUDE.md` for context, so duplication only creates a second place for the
two to drift apart. If a service-local file would just repeat the root
file, don't create it — an empty gap is safer than a stale duplicate.

## 6. Local Onboarding

`README.md` at the repo root documents the minimal path from clone to a
running full stack: `make up` (docker-compose), `make seed` (fixture data),
`make test` (full suite). A new contributor (or a fresh AI agent context)
should be productive within this sequence without needing tribal knowledge.
