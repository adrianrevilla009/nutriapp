# activity-service's Terraform footprint (implementation plan section 3/7):
# mirrors food-recognition-service.tf's structure -- narrowly wires this
# service's Helm release to the shared platform outputs (RDS instance
# endpoint, Secrets Manager entries) provisioned by the platform-infra
# plan, plus this service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as every other
# service.
#
# No JWT signing key, no internal-reveal-credential container, no
# third-party API key: this service issues no tokens, exposes no
# internal non-Kong-routed endpoint, and calls no external API in this
# plan's scope (manual exercise logging only -- implementation plan
# section 1). WearableProviderPort is interface-only with zero
# adapters (implementation plan section 1/9), so there is no wearable
# provider credential to provision here yet either -- a future,
# separately-planned wearable-integration change would add one per
# provider then, not now (see docs/vendor-risk-register.md for the
# "not yet integrated, tracked" note on all four providers).
#
# No ElastiCache usage -- this plan has no caching requirement.

locals {
  activity_service_name      = "activity-service"
  activity_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_activity_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.activity_service_name}"

  tags = merge(local.common_tags, {
    Service = local.activity_service_name
  })
}

# --- Secrets Manager: read the ARN the `secrets` module already
# provisions for this service -- this file does not recreate any secret,
# only references the resulting name/ARN.

locals {
  activity_service_db_credentials_secret_arn = module.secrets.db_credential_secret_arns[local.activity_service_name]
  activity_service_app_secrets_irsa_role_arn = module.secrets.app_secrets_irsa_role_arns[local.activity_service_name]
}

# --- Helm release ---
resource "helm_release" "activity_service" {
  name      = local.activity_service_name
  namespace = local.activity_service_namespace
  chart     = "${path.module}/../../../k8s/charts/activity-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by activity-service-ci.yml at
        # deploy time (`helm upgrade --set image.tag=$GIT_SHA`), never
        # hardcoded in Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_activity_service.repository_url
      }
      secretsManager = {
        dbCredentials = local.activity_service_db_credentials_secret_arn
      }
      serviceAccount = {
        irsaRoleArn = local.activity_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.activity_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.activity_service_name]
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
