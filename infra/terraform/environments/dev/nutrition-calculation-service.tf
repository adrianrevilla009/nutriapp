# nutrition-calculation-service's Terraform footprint (implementation plan
# section 7): mirrors catalog-service.tf's structure -- narrowly wires
# this service's Helm release to the shared platform outputs (RDS
# instance endpoint, Secrets Manager entries) provisioned by the
# companion platform-infra plan, plus this service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as
# identity-service.tf/profile-service.tf/catalog-service.tf.
#
# No JWT signing key, no OWN internal-reveal-credential container: this
# service issues no tokens and exposes no internal, non-Kong-routed
# endpoint of its own. It DOES need read access to a NEW secret it does
# not own -- profile-service's per-caller reveal-metrics credential
# (implementation plan Addendum 1, security sub-addendum requirements 1/2)
# -- provisioned by modules/secrets'
# `profile_reveal_credential_caller_service_names` (this module's own
# addition, reviewed alongside profile-service's coordinated reveal-
# endpoint sub-plan per Addendum 1 item 12) and granted to exactly this
# service's app_secrets IRSA role, nothing else of profile-service's.
#
# Redis: reuses the single shared infra/terraform/modules/elasticache
# cluster (same resolution as catalog-service.tf/diary-service.tf), isolated
# purely by a `nutrition:*` key namespace -- no new ElastiCache cluster.
# `NUTRITION_CALCULATION_SERVICE_REDIS_URL`'s auth-token assembly has the
# same documented gap as catalog-service.tf/identity-service.tf (see that
# file's header comment) -- not resolved here, not silently worked around.

locals {
  nutrition_calculation_service_name      = "nutrition-calculation-service"
  nutrition_calculation_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_nutrition_calculation_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.nutrition_calculation_service_name}"

  tags = merge(local.common_tags, {
    Service = local.nutrition_calculation_service_name
  })
}

# --- Secrets Manager: read the ARNs the platform-infra plan's `secrets`
# module already provisions for this service -- this file does not
# recreate any secret, only references the resulting names/ARNs.

locals {
  nutrition_calculation_service_db_credentials_secret_arn = module.secrets.db_credential_secret_arns[local.nutrition_calculation_service_name]
  nutrition_calculation_service_app_secrets_irsa_role_arn = module.secrets.app_secrets_irsa_role_arns[local.nutrition_calculation_service_name]
  # NEW, narrow exception (Addendum 1 security sub-addendum requirement 2):
  # exactly this ARN, never profile-service's db-credentials or KMS key.
  nutrition_calculation_service_profile_reveal_credential_arn = module.secrets.profile_reveal_credential_secret_arns[local.nutrition_calculation_service_name]
}

# --- Helm release ---
resource "helm_release" "nutrition_calculation_service" {
  name      = local.nutrition_calculation_service_name
  namespace = local.nutrition_calculation_service_namespace
  chart     = "${path.module}/../../../k8s/charts/nutrition-calculation-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by
        # nutrition-calculation-service-ci.yml at deploy time (`helm
        # upgrade --set image.tag=$GIT_SHA`), never hardcoded in
        # Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_nutrition_calculation_service.repository_url
      }
      env = {
        RDS_HOST = module.rds.db_instance_address
        RDS_PORT = module.rds.db_instance_port
      }
      secretsManager = {
        dbCredentials           = local.nutrition_calculation_service_db_credentials_secret_arn
        profileRevealCredential = local.nutrition_calculation_service_profile_reveal_credential_arn
      }
      serviceAccount = {
        irsaRoleArn = local.nutrition_calculation_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.nutrition_calculation_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.nutrition_calculation_service_name]
        image = {
          repository = module.ecr_db_provision.repository_url
          # tag intentionally omitted -- set by the shared
          # db-provision-image-ci.yml workflow at deploy time.
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
