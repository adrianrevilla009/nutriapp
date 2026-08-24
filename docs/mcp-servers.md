# MCP Servers — Catalog & Specification

This document is a **specification and catalog**, not an activation list.
Every MCP server described here is currently **disabled** — none are
wired into `.claude/settings.json` (`mcpServers: {}`). This is deliberate:
the project runs entirely in local development today, and each server
below is added only when its stated **activation condition** is met.

Adding an MCP server to this catalog costs nothing. Cost only appears
once a server is connected *and* used against a paid third-party service —
this document makes that distinction explicit for every entry so the
decision to activate one is never a surprise.

## How to Read Each Entry
- **Status**: always `Disabled (specified)` until explicitly activated by
  a human decision (an ADR is recommended for any entry that requires a
  new paid account).
- **Cost**: whether the server itself and the service it talks to are
  free, free-tier, or paid.
- **Agents**: which `.claude/agents/*` are expected to use it.
- **Activation condition**: the concrete, observable trigger that
  justifies turning it on.
- **Guardrail notes**: anything beyond the general rule in section 5.

---

## 1. GitHub MCP Server
- **Status**: Disabled (specified).
- **Cost**: Free (uses the GitHub API within standard rate limits).
- **Agents**: `devops-agent`, `reviewer-agent`, any agent running
  `/create-pr` or `/create-commit`.
- **Why**: lets agents read existing issues/PRs for context and check CI
  status before proposing a merge, instead of only printing `gh` commands.
- **Activation condition**: as soon as `/create-pr` needs to read live
  PR/CI state rather than just open a PR — i.e. useful from early
  implementation, no infra prerequisite.
- **Example wiring** (only once activated):
  ```json
  {
    "mcpServers": {
      "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" }
      }
    }
  }
  ```
  `GITHUB_TOKEN` lives in the shell environment or a local, gitignored
  `.env` — never hardcoded in `settings.json`.

## 2. Postgres MCP Server (read-only)
- **Status**: Disabled (specified).
- **Cost**: Free — this is the project's own local database.
- **Agents**: `core-domain-agent`, `transaction-agent`, `architecture-agent`.
- **Why**: inspect real schema/data shape during planning without manual
  `psql` output pasted by hand.
- **Activation condition**: as soon as a local Postgres instance exists
  with real schema/data worth inspecting (i.e. after the first service is
  scaffolded).
- **Guardrail notes**: connect only a **read-only** database role — never
  grant this MCP connection write access, in local or any other
  environment.
  ```json
  {
    "mcpServers": {
      "postgres-readonly": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres",
                  "postgresql://readonly_user:${PG_RO_PASSWORD}@localhost:5432/nutriapp"]
      }
    }
  }
  ```

## 3. Slack MCP Server
- **Status**: Disabled (specified).
- **Cost**: Free (Slack's free tier covers a bot posting notifications).
- **Agents**: `devops-agent`, `qa-agent` (for `/test-execution` failure
  notifications).
- **Why**: notify outside the terminal once agents run unattended for
  longer stretches or in a worktree not actively watched.
- **Activation condition**: when unattended/longer-running agent sessions
  actually become a regular workflow — not needed while working
  interactively.

## 4. Browser / E2E MCP Server (e.g. Playwright-based)
- **Status**: Disabled (specified).
- **Cost**: Free, open source.
- **Agents**: `qa-agent` (visual/e2e checks), `catalog-agent` (validating
  real scraping-target behavior manually, never for bulk runs — see
  `.claude/skills/external-data-ethics/SKILL.md`).
- **Why**: lets agents drive a real browser for e2e journeys and for
  ad-hoc inspection of a scraping target's actual page structure.
- **Activation condition**: once `frontend/` exists and end-to-end
  journeys (per `docs/testing-strategy.md`) are being implemented.

## 5. Qdrant MCP Server
- **Status**: Disabled (specified).
- **Cost**: Free if self-hosted (the project's specified deployment, per
  `CLAUDE.md` section 2.5). Paid only if later migrated to Qdrant Cloud.
- **Agents**: `ai-assistant-agent`, `architecture-agent`.
- **Why**: inspect vector collections/embeddings during development of
  the RAG pipeline (see `.claude/skills/rag-conventions/SKILL.md`) without
  writing throwaway inspection scripts.
- **Activation condition**: once a local Qdrant instance is running with
  real collections (i.e. once `nutrition-assistant-service` scaffolding begins).

## 6. Observability MCP — Prometheus + Grafana (free alternative)
- **Status**: Disabled (specified).
- **Cost**: Free, self-hosted — and already the project's specified stack
  (`prometheus-client` in `CLAUDE.md` section 4).
- **Agents**: `infra-agent`, `qa-agent`, `architecture-agent`.
- **Why**: let agents query real metrics/dashboards during incident
  investigation or performance review without a human pasting graphs.
- **Activation condition**: once a local Prometheus/Grafana stack is
  running against at least one service's `/metrics` endpoint.

### 6b. Observability MCP — Datadog (paid alternative, not adopted by default)
- **Status**: Disabled (specified) — documented for completeness only.
- **Cost**: **Paid.** No functional free tier for sustained production
  use; trial only.
- **Agents**: same as 6, if ever adopted in place of Prometheus/Grafana.
- **Activation condition**: only if a future ADR decides to externalize
  observability to a managed vendor for `staging`/`prod` — not planned
  while the project remains self-hosted per `CLAUDE.md` section 2.8.

## 7. Error Tracking MCP — GlitchTip (free alternative)
- **Status**: Disabled (specified).
- **Cost**: Free, self-hosted, open source, Sentry-SDK-compatible.
- **Agents**: `qa-agent`, `security-agent`.
- **Why**: query real captured exceptions/error groups during debugging
  or review without a human pasting stack traces.
- **Activation condition**: once a local GlitchTip instance is running
  and at least one service is configured to report to it.

### 7b. Error Tracking MCP — Sentry (paid-at-scale alternative)
- **Status**: Disabled (specified) — documented for completeness only.
- **Cost**: Free tier exists and may suffice at low volume; **paid**
  beyond that tier.
- **Activation condition**: only if the project later prefers Sentry's
  managed service over self-hosted GlitchTip — a deliberate ADR-level
  decision, not a default.

## 8. Infrastructure MCP — LocalStack (free alternative to a live AWS MCP)
- **Status**: Disabled (specified).
- **Cost**: Free — emulates AWS services locally.
- **Agents**: `infra-agent`.
- **Why**: let `infra-agent` validate Terraform plans and inspect
  emulated AWS resource state without touching a real AWS account or
  incurring any cloud cost, consistent with `CLAUDE.md` section 7 (agents
  never run `terraform apply`/`destroy` against real infrastructure
  regardless).
- **Activation condition**: once Terraform modules exist and need
  iteration/validation before ever pointing at a real AWS account.

### 8b. Infrastructure MCP — live AWS (read-only) (paid-adjacent alternative)
- **Status**: Disabled (specified) — documented for completeness only.
- **Cost**: The MCP connection itself has no license cost; read-only API
  calls against a real AWS account have marginal, usually negligible
  cost, but this operates against **real infrastructure**, unlike
  LocalStack.
- **Activation condition**: only once a real `staging` AWS environment
  exists (per `docs/environments-and-promotion.md`), and only with a
  strictly read-only IAM role — never write/mutating permissions, per
  the guardrails in section 9 below.

## 9. Issue Tracking MCP — GitHub Issues (free, uses entry 1)
- **Status**: Disabled (specified).
- **Cost**: Free — no new tool needed; reuses the GitHub MCP server
  (entry 1) already specified above.
- **Agents**: any agent running `/plan-feature` or `/implementation-plan`
  that needs to reference a tracked piece of work.
- **Why**: keep backlog/planning in one already-specified tool rather than
  introducing a second system for a small team/solo project.
- **Activation condition**: same as entry 1.

### 9b. Issue Tracking MCP — Jira / Linear (paid-at-team-scale alternative)
- **Status**: Disabled (specified) — documented for completeness only.
- **Cost**: Both have limited free tiers; **paid** once the team/project
  count grows past that tier.
- **Activation condition**: only if the project moves to a larger team
  that has already standardized on Jira or Linear outside this repo —
  not a default choice for the current solo/small-team scope.

## 10. Library Documentation MCP (e.g. Context7)
- **Status**: Disabled (specified).
- **Cost**: Free tier covers this project's usage; paid tiers exist for
  very high request volume.
- **Agents**: all domain agents, `architecture-agent` — anyone writing code
  against a fast-moving library (`FastAPI`, `Pydantic v2`, `SQLAlchemy 2.x`,
  `Next.js`, `TanStack Query`).
- **Why**: reduces the single most common failure mode of AI-assisted
  development against a real, versioned stack — an agent confidently
  generating code against an API shape from an older version of a library
  than the one pinned in `pyproject.toml`/`package.json`. This MCP fetches
  current, version-matched documentation instead of relying on training
  data, which is especially relevant for `Pydantic v2` (a frequent source
  of v1-vs-v2 API confusion) and any library still receiving frequent
  breaking releases.
- **Activation condition**: as soon as any service's dependencies are
  pinned (i.e. from the very first service scaffold) — there is no
  meaningful reason to delay this one relative to the others in this
  catalog, since it costs nothing and has no infrastructure prerequisite.
- **Guardrail notes**: read-only by nature (fetches public documentation);
  no data-exposure concern beyond the library/version names being queried.

## 11. Filesystem / Fetch MCP Servers
- **Status**: Not planned.
- **Note**: Claude Code's built-in tools already cover local file access
  and web fetch. Only add a dedicated MCP server here if a future need
  requires sandboxed access scoped differently from Claude Code's
  defaults — no current activation condition exists.

---

## Guardrails for Any MCP Connection (applies to every entry above)
- Never connect an MCP server with write access to production data,
  regardless of cost tier.
- Prefer the free/self-hosted alternative unless a specific, documented
  reason requires the paid one (vendor support, team-wide existing
  adoption, compliance requirement) — record that reason in an ADR.
- Any MCP tool that can push, merge, delete, or notify externally is
  subject to the same human-in-the-loop confirmation rules as `Bash`
  tools — extend `.claude/hooks/pre-bash-guard.sh` patterns to cover MCP
  tool names before activating any such server.
- Activating a server means: (1) confirming its activation condition is
  met, (2) adding real config under `mcpServers` in
  `.claude/settings.json`, (3) recording the change in `STATUS.md` (see
  `docs/project-status-tracking.md`), and (4) updating this document's
  **Status** field for that entry — activation is itself a tracked
  change, not a silent edit.
