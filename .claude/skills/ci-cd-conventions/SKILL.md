---
description: CI/CD pipeline conventions for NutriApp (GitHub Actions, path-filtered per service). Use whenever creating or modifying a workflow file, a Dockerfile build stage used in CI, or discussing what gates a merge/deploy.
---

# CI/CD Conventions — NutriApp

Full policy: `docs/ci-cd-strategy.md`. This is the quick reference for
writing or editing a workflow.

## Workflow File Naming & Triggers
- One workflow per service: `.github/workflows/<service-name>-ci.yml`,
  triggered `on: pull_request` and `on: push: branches: [main]`, with a
  `paths:` filter scoped to `services/<service-name>/**` and
  `packages/shared-contracts/**`.
- A separate `infra-ci.yml` for `infra/terraform/**` changes (plan only, never
  apply — see below).

## Stage Order (fail fast)
lint -> type-check -> secret-scan -> unit -> dep-vuln-scan -> integration ->
contract -> coverage-gate -> build-image -> image-scan -> push -> deploy-dev
-> smoke-e2e -> promote-staging -> **manual-approval** -> promote-prod.

## Rules
- Never skip a stage to "speed things up" — reorder if something can run in
  parallel, don't remove a gate.
- `terraform apply` and `terraform destroy` NEVER run in an automated
  workflow step, only `plan`. See `.claude/hooks/pre-terraform-guard.sh` and
  `docs/terraform-and-infrastructure.md` section 4.
- Production deploy jobs use `environment: production` with required
  reviewers configured in repo settings — do not attempt to bypass this with
  a workaround workflow.
- Any new external Action pinned to a full commit SHA, not a mutable tag
  (supply-chain hygiene).

## Pre-commit
`.pre-commit-config.yaml` at repo root mirrors the CI lint/type-check/secret-
scan stages locally. Run it (or ensure `/create-commit` has run it) before
proposing any commit.
