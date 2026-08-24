# ADR-0007: AWS Secrets Manager + External Secrets Operator for secrets

## Status
Accepted

## Date
2026-08-23

## Context
Every service needs database credentials, the JWT signing key pair, RabbitMQ
credentials, third-party API keys (vision API, LLM provider), and Qdrant
credentials. These must never live in git, must be injectable into Kubernetes
pods without hand-copying, and must support rotation without redeploying
application code.

## Decision
Use **AWS Secrets Manager** as the single source of truth for all
production/staging secrets, synced into Kubernetes as native `Secret` objects
via the **External Secrets Operator (ESO)**. Application code reads secrets
only from environment variables or mounted files populated by Kubernetes —
never calls AWS APIs directly to fetch a secret at runtime (keeps the domain
and application layers free of infra dependencies, per the hexagonal rule).

Local development uses a git-ignored `.env` file per service, seeded from
`.env.example` (placeholders only, committed).

RDS-managed secrets (master password rotation) use Secrets Manager's native
RDS rotation Lambda. Application-level secrets (JWT signing key, third-party
API keys) are rotated manually on a documented schedule until volume justifies
automating each one individually.

## Considered Alternatives
- **HashiCorp Vault** — more powerful (dynamic secrets, fine-grained leasing),
  but another stateful service to operate (HA, unsealing, backup) for
  marginal benefit at this scale. Rejected for now; revisit if dynamic
  short-lived database credentials become a hard requirement.
- **Kubernetes Secrets only (no external store)** — simplest, but secrets end
  up base64-encoded (not encrypted at rest, by default) sitting in etcd and
  in git if anyone commits a manifest by mistake. Rejected as insufficient for
  production data-of-health-nature.
- **SSM Parameter Store instead of Secrets Manager** — cheaper, but lacks
  native rotation Lambdas for RDS and has stricter throughput limits. Secrets
  Manager chosen for the built-in RDS rotation integration.

## Consequences
### Positive
- No secret ever needs to be manually copy-pasted into a running cluster;
  ESO reconciles continuously.
- Native RDS rotation removes a recurring manual security task.
- IAM policy (via IRSA — IAM Roles for Service Accounts) scopes exactly which
  secrets each service's pod can read, enforcing least privilege at the
  infrastructure level, not just documentation.

### Negative / Trade-offs
- Adds AWS cost (Secrets Manager charges per secret per month) — acceptable
  at this scale, tracked in `docs/cost-management.md`.
- ESO is another controller to keep updated in the cluster.
- Non-RDS secrets (third-party API keys) still require a manual rotation
  runbook until rotation is automated per-integration.

### Follow-up actions
- Write the ESO `SecretStore`/`ExternalSecret` manifests per service in
  `infra/k8s/`.
- Document the manual rotation runbook for third-party API keys in
  `docs/secrets-management.md`.
- Configure IRSA roles in Terraform (`infra/terraform/modules/secrets/`).

## References
- `docs/secrets-management.md`
- `docs/security-and-compliance.md`
- ADR-0006 (EKS)
