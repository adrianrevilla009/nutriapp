# Environments & Promotion

## 1. Environments

| Environment | Purpose                                      | Data                                    | Access                          |
|--------------|-------------------------------------------------|----------------------------------------------|-------------------------------------|
| `dev`         | Agent-driven development, integration testing         | Synthetic/seeded fixture data only, never real user data | Any contributor/agent |
| `staging`      | Pre-prod validation, E2E, load testing, DR drills          | Anonymized copy of prod-shaped data or synthetic data at prod scale — never a raw prod data copy | Human approval to refresh |
| `prod`          | Real users                                                   | Real user data                                                     | Human approval for every deploy and every infra change |

Real (non-anonymized) user data never leaves `prod`. Seeding `staging` with
realistic data means generating synthetic data at similar scale/shape, or
applying an anonymization pipeline (hashing/replacing identifiers, dropping
free-text fields) to a prod export — never a raw copy, given the health-data
sensitivity discussed in `docs/data-protection-and-privacy.md`.

## 2. Promotion Path

```
feature branch -> PR -> CI gates pass -> merge to main
                                              |
                                              v
                                    auto-deploy to dev
                                              |
                                    dev smoke tests pass
                                              |
                                              v
                                  auto-promote to staging
                                              |
                          staging E2E + load tests pass (pre-release changes)
                                              |
                                              v
                              MANUAL APPROVAL (human, named reviewer)
                                              |
                                              v
                                     deploy to prod
                                              |
                                   prod smoke tests + SLO watch
```

- `dev` and `staging` promotion is automatic on passing gates — fast feedback
  matters more than ceremony at those stages.
- `prod` promotion always requires a named human approval in the GitHub
  Actions `environment: production` protection rule, regardless of how
  confident the agent pipeline is. This is the same non-negotiable
  human-in-the-loop principle as CLAUDE.md section 6, applied to deployment
  rather than code review.

## 3. Rollback

- Every `prod` deploy is a Helm release with a retained history
  (`helm history`); rollback is `helm rollback <release> <revision>`,
  targeted to complete within the RTO defined in
  `docs/backup-and-disaster-recovery.md`.
- Database migrations follow the expand/contract pattern (CLAUDE.md 2.5)
  specifically so a code rollback never requires a matching destructive
  schema rollback.
- A rollback is a normal, expected operational action, not treated as a
  failure requiring the full change-approval pipeline to reverse — but it
  does require a human to trigger it, and it always produces an incident
  entry (`docs/incident-response.md`) if it followed a user-facing issue.

## 4. Feature Flags Across Environments

New, risky, or partially-implemented behavior ships behind a flag (see
`docs/feature-flags.md`) so it can reach `prod` disabled, then be enabled
progressively without a redeploy — decoupling *deploy* from *release*.

## 5. Configuration Per Environment

- Non-secret configuration lives in each service's Helm `values-<env>.yaml`.
- Secret configuration is never environment-specific in git — it's the same
  Secrets Manager path structure with environment-specific values, per
  `docs/secrets-management.md`.
- No environment-specific code branches (`if env == "prod"` in application
  code) beyond what dependency injection/configuration already handles —
  behavior differences are configuration, not code forks.
