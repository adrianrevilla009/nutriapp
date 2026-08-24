# modules/secrets

Secrets Manager baseline + IRSA IAM policies (ADR-0007). See
`docs/secrets-management.md` and the implementation plan section 9.1 for
the full per-service database credential flow this module is one half
of (the other half is `infra/k8s/charts/_lib/templates/_db-provision-job.tpl`).

## Naming convention every consuming service's Helm chart MUST match

For a service listed in `var.db_credential_service_names` (e.g.
`"identity-service"`), this module creates two IRSA roles, each trusting
a specific Kubernetes ServiceAccount name in the shared namespace
(`var.namespace`, default `nutriapp-dev`):

| Role | Trusts ServiceAccount | Used by |
|---|---|---|
| `nutriapp-<env>-<service>-db-provision` | `<service>-db-provision` | the `_db-provision-job` hook's Job |
| `nutriapp-<env>-<service>-app-secrets` | `<service>` | the service's own app Deployment |

If a consuming chart names its ServiceAccounts differently, the IRSA
trust policy's `sub` condition will not match and
`AssumeRoleWithWebIdentity` will fail at pod startup — this is
enforced by AWS, not just documentation.

## What this module does NOT do

- Does not generate or store any per-service database password —  it
  only creates the empty (placeholder) Secrets Manager container the
  `_db-provision-job` Job writes into on first run. See that template's
  header comment for why (no Terraform network path into the
  private-subnet RDS instance).
- Does not create a single shared/"god" IAM role that can read every
  service's secrets — each service gets its own narrowly-scoped
  `app-secrets` role, per `docs/secrets-management.md` section 4.
