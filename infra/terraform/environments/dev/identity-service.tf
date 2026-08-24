# identity-service's Terraform footprint (implementation plan §7):
# narrowly wires this service's Helm release to the shared platform
# outputs (RDS instance endpoint, Secrets Manager entries) provisioned by
# the companion platform-infra plan (/plans/platform-infra/implementation-plan.md).
#
# Deliberately does NOT create the service's database via a Terraform
# `postgresql` provider resource — per the platform-infra plan's resolved
# decision (§9.1), that provider has no network path into the
# private-subnet RDS instance from a human's laptop or a CI runner. The
# per-service database/role is instead created by a Kubernetes Job
# (`_db-provision-job` template in infra/k8s/charts/_lib/) that runs as a
# pre-install/pre-upgrade hook on this service's own Helm release.
#
# References module.rds / module.secrets / module.eks from the
# platform-infra plan's modules (infra/terraform/environments/dev/main.tf),
# which now exist in this repo. Output names below were reconciled against
# the actual module outputs (infra/terraform/modules/rds/outputs.tf,
# infra/terraform/modules/secrets/outputs.tf) after both plans' execution
# agents ran concurrently and initially disagreed on naming — see
# /plans/platform-infra/implementation-plan.md for the resolved contract.
#
# The `internal-reveal-credential` secret (used to authenticate
# notification-service's future call to the internal token-reveal
# endpoint, per the reference+secret pattern) was not part of the
# originally approved platform-infra plan scope — it was added to
# infra/terraform/modules/secrets/ as a follow-up, human-approved
# reconciliation step, following the same per-service container pattern
# as jwt-signing-key/db-credentials.

locals {
  identity_service_name      = "identity-service"
  identity_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_identity_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.identity_service_name}"

  tags = merge(local.common_tags, {
    Service = local.identity_service_name
  })
}

# --- Secrets Manager: read the ARNs the platform-infra plan's `secrets`
# module already provisions for this service — this file does not
# recreate any secret, only references the resulting names/ARNs to pass
# into the Helm release below. All three come from module.secrets'
# per-service map outputs (infra/terraform/modules/secrets/outputs.tf),
# keyed by "identity-service", not from separate `data` lookups — the
# ARNs are already known within this same Terraform run.

locals {
  identity_jwt_signing_key_secret_arn     = module.secrets.jwt_signing_key_secret_arns[local.identity_service_name]
  identity_db_credentials_secret_arn      = module.secrets.db_credential_secret_arns[local.identity_service_name]
  identity_internal_reveal_credential_arn = module.secrets.internal_reveal_credential_secret_arns[local.identity_service_name]
  identity_app_secrets_irsa_role_arn      = module.secrets.app_secrets_irsa_role_arns[local.identity_service_name]
}

# --- Helm release ---
# References the shared RDS instance's connection outputs and the
# Secrets Manager entries above; does not create the database itself
# (see file header). `module.rds`, `module.eks`, and `module.secrets`
# come from the platform-infra plan (infra/terraform/environments/dev/main.tf).
resource "helm_release" "identity_service" {
  name      = local.identity_service_name
  namespace = local.identity_service_namespace
  chart     = "${path.module}/../../../k8s/charts/identity-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted here — set by identity-service-ci.yml
        # at deploy time (`helm upgrade --set image.tag=$GIT_SHA`), never
        # hardcoded in Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_identity_service.repository_url
      }
      env = {
        RDS_HOST = module.rds.db_instance_address
        RDS_PORT = module.rds.db_instance_port
      }
      secretsManager = {
        dbCredentials            = local.identity_db_credentials_secret_arn
        jwtSigningKeyPair        = local.identity_jwt_signing_key_secret_arn
        internalRevealCredential = local.identity_internal_reveal_credential_arn
      }
      # values.yaml's serviceAccount.irsaRoleArn is the exact key
      # infra/k8s/charts/_lib/templates/_serviceaccount.tpl requires —
      # NOT nested under `annotations` (a prior mismatch here made this
      # chart fail its `required(...)` render guard entirely, caught in
      # /implementation-review).
      serviceAccount = {
        irsaRoleArn = local.identity_app_secrets_irsa_role_arn
      }
      # _db-provision-job.tpl input (infra/k8s/charts/_lib) — creates this
      # service's own logical database/role inside the shared RDS instance
      # at Helm-release time, per the platform-infra plan's §9.1 resolved
      # decision. irsaRoleArn is deliberately the *db-provision* role, not
      # the app's own serviceAccount role above — two distinct, narrowly
      # scoped IRSA roles per docs/secrets-management.md section 4.
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.identity_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.identity_service_name]
        image = {
          repository = module.ecr_db_provision.repository_url
          # tag intentionally omitted — set by the shared
          # db-provision-image-ci.yml workflow at deploy time, same
          # pattern as the app image above.
        }
      }
    })
  ]

  depends_on = [
    module.eks,
    module.rds,
    module.secrets,
  ]
}
