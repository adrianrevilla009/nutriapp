---
description: Static code quality thresholds (complexity, duplication, maintainability) enforced via SonarQube, complementing test coverage. Use whenever implementing or reviewing any non-trivial function, or before marking implementation complete.
---

# Code Quality Gates

Full rationale and tooling: `docs/code-quality.md`. Quick-reference
thresholds an agent checks against before considering implementation done.

## Thresholds (see `docs/code-quality.md` section 2 for the full table)
- Cyclomatic complexity: flag > 10, block > 15 per function.
- Duplication: < 3% duplicated lines per service.
- Maintainability rating: A or B.
- Zero unreviewed security hotspots at merge.

## Before Marking Implementation Complete
1. Run the configured static analysis (`sonar-scanner` or project
   equivalent) against the diff — not the whole codebase, consistent
   with how coverage and SAST are already scoped to diffs on PRs
   (`docs/ci-cd-strategy.md`).
2. If a new function exceeds the complexity threshold: refactor it
   (extract sub-functions, simplify branching) rather than requesting an
   exception — high complexity in new code is a design smell to fix now,
   when the context is fresh, not a debt to accumulate.
3. If a genuine false positive occurs (rare): mark it as a reviewed
   exception in SonarQube with a comment explaining why, never by
   disabling the rule project-wide.
4. For the domain layer specifically (`.claude/skills/hexagonal-architecture/SKILL.md`,
   `.claude/skills/domain-calculation-conventions/SKILL.md`): treat any
   complexity or duplication finding with extra weight — this is the
   layer most worth keeping simple and correct, per those skills'
   existing correctness-sensitivity guidance.

## Rules
- Pre-existing code failing the gate is not retroactively blocking —
  don't propose a "refactor everything" task with no attached product
  value; pay down debt opportunistically alongside related feature work.
- Never lower a project-wide quality-gate threshold to make a specific
  PR pass — fix the code, or get an explicit, documented, human-approved
  exception for that one case.
- A quality-gate failure blocks merge with the same severity as a
  coverage-gate failure (`docs/ci-cd-strategy.md` step 9) — do not treat
  it as advisory.

## Output Format (when reporting on quality gate results)
Summarize: complexity/duplication findings on the diff, whether the gate
passed, and any exception requested with its justification.
