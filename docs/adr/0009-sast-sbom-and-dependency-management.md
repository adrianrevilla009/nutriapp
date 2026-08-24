# ADR-0009: Static Analysis (SAST), SBOM Generation, and Proactive Dependency Updates

## Status
Accepted

## Date
2026-08-23

## Context
The existing CI/CD pipeline (`docs/ci-cd-strategy.md`) already runs linting
(`ruff`/`eslint`), a secret scanner (`gitleaks`), dependency vulnerability
scanning at PR time (`pip-audit`/`npm audit`), and a container image scan
(`Trivy`). Three gaps remain that a code style linter or a known-CVE
database cannot catch:
1. **Semantic vulnerability patterns** in first-party code (SQL built via
   string concatenation despite the ORM rule, insecure deserialization,
   SSRF-prone HTTP calls, hardcoded crypto misuse) — a lint rule doesn't
   catch these; a security-focused static analyzer does.
2. **Supply-chain provenance** — knowing *what* is actually shipped in a
   given image (exact package + version graph), independent of whether a
   CVE is known today, matters for future audits and for fast triage when
   a new CVE is announced for a package already in production.
3. **Reactive-only dependency hygiene** — the existing PR-time scan blocks
   on a *known* CVE, but does nothing to keep dependencies current
   *before* they become one, letting version drift accumulate silently.

## Decision
Add three complementary mechanisms, all free/open-source, none requiring a
new paid vendor:
- **SAST**: `semgrep` (Python + TypeScript rulesets, including the
  `p/owasp-top-ten` and `p/fastapi` packs) runs as its own CI stage,
  between step 2 (type check) and step 3 (secret scan) in
  `docs/ci-cd-strategy.md`. Blocking on `ERROR`-severity findings; `WARNING`
  findings are visible in the PR but non-blocking, reviewed by
  `security-agent`.
- **SBOM**: `syft` generates a CycloneDX SBOM for every built container
  image, attached as a build artifact and stored alongside the image tag in
  ECR (as an OCI artifact, not just a file dropped in CI logs), so it's
  retrievable for any image later without rebuilding.
- **Proactive updates**: **Dependabot** (native GitHub integration, zero
  extra infra) opens weekly PRs per ecosystem, per
  `.github/dependabot.yml`. These PRs go through the same human-in-the-loop
  pipeline as any other change — never auto-merged, per CLAUDE.md section 6
  — but a major-framework bump gets `devops-agent` + `architecture-agent`
  review specifically for breaking-change risk.

## Considered Alternatives
- **Snyk** (SAST + SCA + container scanning, unified paid platform) —
  stronger single-pane-of-glass UX, but paid beyond a small free tier and
  duplicates capability already covered for free by `semgrep` + `Trivy` +
  `pip-audit`/`npm audit`. Rejected for the same reason `docs/mcp-servers.md`
  prefers free/self-hosted alternatives by default; revisit via a new ADR
  if the project scales to a size where a unified vendor's triage UX
  outweighs its cost.
- **Renovate instead of Dependabot** — comparable capability,
  self-hostable, more configurable grouping/scheduling rules. Dependabot
  chosen for zero additional infrastructure (native to GitHub, which the
  project already uses per ADR-0005); revisit if Renovate's grouping rules
  become necessary as the number of services grows.
- **CodeQL instead of Semgrep** — GitHub-native, strong for larger
  codebases, but higher CI minutes cost and steeper custom-rule authoring.
  Semgrep chosen for faster CI runtime and simpler custom rules (e.g.
  enforcing "no raw SQL string interpolation" as a project-specific rule
  beyond generic OWASP patterns).

## Consequences
### Positive
- Catches a class of vulnerability (logic/pattern-level) that no existing
  stage covers.
- SBOM answers "are we affected by CVE-X" in seconds once it's announced,
  without re-scanning every image.
- Dependency drift no longer accumulates silently between CVE-triggered
  scans.

### Negative / Trade-offs
- One more CI stage (Semgrep) adds runtime; mitigated by running it only on
  the diff for PRs, full-repo scan only on `main`.
- Dependabot PR volume can be noisy for actively-changing services early
  on; grouped updates (same ecosystem, same week) keep this manageable.

### Follow-up actions
- Add the Semgrep and SBOM steps to `docs/ci-cd-strategy.md`'s numbered
  pipeline.
- Add `.github/dependabot.yml` (done).
- `security-agent` reviews the first month of Semgrep findings to tune
  custom rules and reduce false positives before the gate is made strict.

## References
- `docs/ci-cd-strategy.md`
- `docs/supply-chain-security.md`
- `.github/dependabot.yml`
