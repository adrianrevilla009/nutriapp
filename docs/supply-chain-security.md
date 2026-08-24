# Supply Chain & Static Security

Full rationale: ADR-0009. This document is the day-to-day reference for
`security-agent` and `devops-agent`; the CI mechanics live in
`docs/ci-cd-strategy.md`.

## 1. The Four Layers

| Layer                        | Tool                | Catches                                   | Runs when                     |
|-------------------------------|----------------------|--------------------------------------------|----------------------------------|
| Secret scan                  | `gitleaks`           | Committed credentials                     | Every PR, on the diff            |
| SAST                          | `semgrep`            | Vulnerable code patterns (first-party)    | Every PR (diff), full scan on `main` |
| SCA (known CVEs)              | `pip-audit`/`npm audit` | Known-vulnerable dependency versions   | Every PR                         |
| Container scan                | `Trivy`               | Known-vulnerable OS/package layers        | Every image build                |
| SBOM                          | `syft`                | Full provenance (what's actually shipped) | Every image build (informational, non-blocking) |
| Proactive dependency updates  | `Dependabot`          | Version drift before it becomes a CVE     | Weekly, per `.github/dependabot.yml` |

No single layer replaces another — a dependency can be a known-CVE match
(SCA) with a fully patched version already in `pyproject.toml` (making it a
false SCA hit until upgraded) while simultaneously the first-party code
around it does something a CVE database will never flag (SAST's job).

## 2. SAST (Semgrep) Rules

- Rulesets: `p/owasp-top-ten`, plus a project-specific ruleset under
  `.semgrep/nutriapp-rules.yml` enforcing conventions that are
  project-specific, not generic OWASP (e.g. "no `text()` raw SQL construction
  outside `infrastructure/persistence/`", "no `eval`/`exec` anywhere",
  "food-recognition-service image bytes never logged at any log level" — see
  `.claude/skills/media-recognition-conventions/SKILL.md`).
- `ERROR` severity blocks the PR. `WARNING` severity is visible but
  non-blocking; `security-agent` triages these weekly rather than gating
  every PR on tuning noise.
- False positives are suppressed with an inline `# nosemgrep: rule-id` and a
  one-line justification comment — never a blanket ignore of a whole file
  or rule.

## 3. SBOM

- Generated per image at build time (CycloneDX format), stored as an OCI
  artifact alongside the image in ECR — retrievable for any previously
  shipped image without a rebuild.
- Used reactively: when a new CVE is announced for a library, `security-agent`
  queries stored SBOMs (once the Postgres/observability MCP tooling in
  `docs/mcp-servers.md` is extended, or manually via `syft`/`grype` CLI) to
  find every affected image across every environment in minutes, not hours.

## 4. Dependency Update Policy

- Dependabot opens PRs per `.github/dependabot.yml`, grouped weekly per
  ecosystem.
- Patch/minor version bumps: reviewed like any other PR, no special gate.
- Major version bumps of a core framework (FastAPI, Pydantic, Next.js,
  SQLAlchemy): requires `devops-agent` and `architecture-agent` review
  specifically for breaking-change risk before the human approval gate —
  same pipeline as any change, just with named required reviewers.
- Security-only Dependabot alerts (not version-bump PRs) are triaged within
  1 business day for `critical`/`high` severity, per the response times in
  `docs/incident-response.md`.

## 5. What This Does Not Cover

- **DAST** (dynamic application security testing against a running
  `staging` environment) is not yet adopted — revisit once `staging` is a
  stable, always-on environment (per `docs/environments-and-promotion.md`)
  worth running an OWASP ZAP baseline scan against on a schedule.
- **Penetration testing** by a third party is a pre-launch/annual activity,
  not a CI concern — track as a `docs/project-status-tracking.md` milestone
  once a real production launch date exists, not before.
