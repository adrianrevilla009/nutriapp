---
description: Supply chain and static security conventions for NutriApp (SAST, SBOM, dependency updates). Use whenever writing code that touches SQL construction, deserialization, external HTTP calls, or cryptography, and whenever reviewing a Dependabot PR.
---

# Supply Chain Security Conventions — NutriApp

Full policy: `docs/supply-chain-security.md`. ADR: ADR-0009.

## Rules
- Never build SQL via string interpolation/concatenation, even for a
  "trusted" internal value — use SQLAlchemy Core/ORM parameterization always.
  This is both an `api-conventions` rule and a Semgrep-enforced one; a
  Semgrep `ERROR` here blocks the PR, it is not a style suggestion.
- Never `eval`/`exec` on any input, including config values loaded at
  startup.
- Any outbound HTTP call built from user-influenced input (URL, host, or
  path segment) must validate against an explicit allowlist — never
  construct a fetch target purely from request data (SSRF prevention).
- If Semgrep flags a real false positive, suppress with
  `# nosemgrep: <rule-id>` and a one-line justification comment on the same
  line or the line above — never a file-level or rule-wide ignore.
- A Dependabot PR bumping a **major** version of a core framework (FastAPI,
  Pydantic, SQLAlchemy, Next.js) is never merged without `devops-agent` and
  `architecture-agent` review for breaking changes — treat it like any other
  implementation change requiring the human-in-the-loop pipeline, not a
  rubber-stamp merge.
- `food-recognition-service` image bytes are never written to any log, at any log
  level, under any circumstance — enforced as a project-specific Semgrep
  rule, not just a code-review reminder. See
  `.claude/skills/media-recognition-conventions/SKILL.md`.

## When implementing a new service or endpoint
1. Confirm no raw string SQL exists — grep for `text(` outside
   `infrastructure/persistence/` before considering the work done.
2. Confirm any new outbound call target is either a fixed, hardcoded URL or
   validated against an allowlist.
3. If adding a new external dependency, prefer one already in
   `docs/mcp-servers.md`'s or `CLAUDE.md` section 4's approved stack before
   introducing a new library for the same job.
