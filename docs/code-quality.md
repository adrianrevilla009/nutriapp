# Code Quality Gates

Complements `docs/testing-strategy.md` (which covers test coverage
thresholds) with **static code quality**: maintainability, duplication,
complexity, and code smells — dimensions coverage percentage alone does
not capture. See `.claude/skills/code-quality-gates/SKILL.md` for the
quick-reference version agents load during implementation.

## 1. Tooling

**SonarQube Community Edition, self-hosted** — consistent with this
project's general bias toward open/self-hostable tooling over paid SaaS
(the same pattern `docs/mcp-servers.md` applies to Prometheus/Grafana
over Datadog, GlitchTip over Sentry, self-hosted PostHog over Amplitude
in ADR-0013). SonarCloud (hosted, free for public repos) is an acceptable
alternative if the repository is public — do not pay for SonarCloud on a
private repo when self-hosted Community Edition covers the same checks.

## 2. What Is Measured (beyond `docs/testing-strategy.md`'s coverage %)

| Dimension | Threshold | Why it's separate from coverage |
|---|---|---|
| Cyclomatic complexity | Flag any function above 10 (Sonar default), block above 15 | High coverage can coexist with unreadable, hard-to-modify logic |
| Duplication | < 3% duplicated lines per service | Coverage doesn't catch copy-pasted logic that will drift out of sync |
| Maintainability rating | A or B (Sonar's technical-debt-ratio grade) | Aggregates code smells into a single trend metric over time |
| Reliability rating | A or B | Sonar's own bug-pattern detection, complementary to (not a replacement for) the SAST rules in `docs/supply-chain-security.md` |
| Security hotspots | Zero unreviewed hotspots at merge | Complementary to Semgrep (`docs/supply-chain-security.md`) — Sonar's security-hotspot detection uses a different rule engine and catches different patterns; running both is deliberate redundancy for this specific concern, not duplication |

## 3. Quality Gate Definition

- A **quality gate** is a named, versioned set of the thresholds above,
  applied per-PR on the **diff** (new/changed code), not retroactively on
  the whole codebase — consistent with how `docs/ci-cd-strategy.md`
  already scopes SAST to diffs on PRs and full scans on `main`.
- New code failing the quality gate **blocks merge**, same severity as
  the coverage gate in `docs/ci-cd-strategy.md` step 9.
- Pre-existing code that doesn't meet the gate is **not** retroactively
  blocking — track it as accumulated technical debt (Sonar's own debt
  metric) and pay it down opportunistically, never as a blanket
  "refactor everything" task with no product value attached.

## 4. CI Integration

Add as a step in `docs/ci-cd-strategy.md`'s pipeline, positioned after
the coverage gate and before the image build step (fail fast on quality
before spending time building an image):

```
lint -> tests -> coverage gate -> quality gate (Sonar) -> image scan -> deploy-dev -> ...
```

## 5. Rules for Agents

- Before marking an implementation complete, run the local quality check
  (`sonar-scanner` in local/CI mode, or the project's configured
  equivalent) against the diff, the same way `docs/testing-strategy.md`
  already expects coverage to be checked before `/test-execution` is
  considered done.
- A quality-gate failure is treated as a defect to fix, not a threshold
  to negotiate down — if a genuine false positive occurs, mark it as a
  reviewed, justified exception in SonarQube itself (with a comment
  explaining why), never by lowering the project-wide threshold to
  accommodate one case.
- Complexity/duplication findings in the domain layer specifically are
  held to the same rigor as the correctness-sensitive testing
  requirements in `.claude/skills/domain-calculation-conventions/SKILL.md`
  — this is where unreviewed complexity is most expensive to carry.

## 6. Ownership

`qa-agent` owns the quality gate configuration and enforces it during
`/test-review`. `reviewer-agent` treats an override of a quality-gate
failure with the same seriousness as an override of a coverage threshold
— it requires an explicit, documented justification, not a silent skip.
