# CI/CD Strategy

Full specification behind CLAUDE.md's CI/CD summary. Reference for
`devops-agent` and for `.github/workflows/`. See ADR-0005 for the monorepo
rationale.

## 1. Principles

- **Path-filtered, per-service pipelines.** A change under `services/diary-service/`
  triggers only that service's pipeline, plus contract-test verification for
  any service that consumes an event or API `diary-service` owns.
- **Fail fast, fail cheap.** Lint and type-check run before any container is
  built or any integration test spins up infrastructure.
- **No pipeline deploys to production without a human gate**, mirroring the
  human-in-the-loop workflow in CLAUDE.md section 6. CI can deploy to `dev`
  automatically on merge to `main`; `staging` requires a passing `dev` smoke
  test; `prod` requires an explicit manual approval step in GitHub Actions
  (`environment: production` with required reviewers).

## 2. Pipeline Stages (per service)

1. **Lint & format check** — `ruff check`, `ruff format --check` (Python);
   `eslint`, `prettier --check` (frontend/TypeScript).
2. **Type check** — `mypy --strict` (Python); `tsc --noEmit` (TypeScript).
3. **Secret scan** — `gitleaks detect` on the diff, blocking on any match.
4. **SAST** — `semgrep` against the diff (full-repo scan on `main`),
   blocking on `ERROR`-severity findings. See
   `docs/supply-chain-security.md` section 2.
5. **Unit tests** — `pytest -m unit` (or equivalent), no external
   dependencies, must complete in under 2 minutes per service.
6. **Dependency vulnerability scan** — `pip-audit` / `npm audit --production`,
   blocking on high/critical severity.
7. **Integration tests** — `pytest -m integration` against `testcontainers`
   (Postgres, RabbitMQ, Redis, Qdrant as needed).
8. **Contract tests** — verify the service's API against its OpenAPI spec and
   its published events against `docs/events-catalog.md`; also run consumer
   contract tests for any service that depends on this one's contracts.
9. **Coverage gate** — enforce per-layer thresholds from
   `docs/testing-strategy.md` section 3; block merge if unmet.
10. **Code quality gate** — SonarQube analysis against the diff (complexity,
    duplication, maintainability, security hotspots); block merge if unmet,
    per `docs/code-quality.md`.
11. **Build container image** — multi-stage Docker build (see
    `docs/containerization-and-orchestration.md`), tagged with the git SHA.
12. **Image vulnerability scan** — Trivy against the built image, blocking on
    critical CVEs with no available fix suppressed via a documented,
    time-boxed exception file.
13. **SBOM generation** — `syft` generates a CycloneDX SBOM for the image,
    stored as an OCI artifact alongside it in ECR (non-blocking,
    informational — see `docs/supply-chain-security.md` section 3).
14. **Push to registry** — Amazon ECR, one repository per service.
15. **Deploy to `dev`** — `helm upgrade` via the service's chart (or the
    canary/blue-green controller once ADR-0017 activates it), automatic on
    merge to `main`.
16. **E2E smoke tests** — run against `dev` post-deploy, not on every PR (per
    `docs/testing-strategy.md` section 7).
17. **Promote to `staging`** — automatic if `dev` smoke tests pass.
18. **Promote to `prod`** — manual approval required (see
    `docs/environments-and-promotion.md`).

Dependency updates are also handled **proactively**, outside this per-PR
pipeline: see `.github/dependabot.yml` and `docs/supply-chain-security.md`
section 4.

## 3. Pre-commit (before CI even runs)

`.pre-commit-config.yaml` at the repo root runs locally on every commit:
- `ruff`, `ruff-format`, `mypy` (Python changed files)
- `eslint`, `prettier` (TypeScript/frontend changed files)
- `gitleaks` (secret detection)
- `check-added-large-files`, `end-of-file-fixer`, `trailing-whitespace`
- Conventional commit message validation (`commitlint`)

Pre-commit does not replace CI — it exists to catch trivial issues before they
consume CI minutes, and agents must run it locally (or via the
`/create-commit` command) before proposing a commit.

## 4. Terraform Pipeline (separate workflow)

Infrastructure changes (`infra/terraform/**`) run a distinct pipeline:
1. `terraform fmt -check`
2. `terraform validate`
3. `tflint`
4. `checkov` or `tfsec` (security/misconfiguration scan)
5. `terraform plan` — output posted as a PR comment for human review
6. **`terraform apply` never runs automatically.** It requires a human to
   run it locally or approve a manual-trigger workflow, exactly like
   `git push` and destructive migrations under CLAUDE.md section 7. See
   `.claude/hooks/pre-terraform-guard.sh`.

## 5. Branching & Commits

- Trunk-based development: short-lived feature branches off `main`, merged
  via PR after all gates pass.
- Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`,
  `chore:`), scoped to the service touched when relevant
  (`feat(diary-service): ...`), generated via `/create-commit`.
- PRs are opened via `/create-pr`, description auto-populated from the
  implementation plan and review findings (CLAUDE.md section 6, steps 11-12).

## 6. Required Status Checks

A PR cannot merge unless every stage above (for every service it touches)
reports success, `reviewer-agent`'s `/implementation-review` verdict is
CLEARED or CLEARED WITH NOTES, and `/test-review` confirms coverage and test
quality. `CODEOWNERS` requires review from the relevant domain agent's human
counterpart before merge, even in a solo project — this is a deliberate
forcing function, not bureaucracy for its own sake.
