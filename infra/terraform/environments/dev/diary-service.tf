# diary-service's Terraform footprint (implementation plan section 7):
# mirrors profile-service.tf's structure minus the KMS block -- diary
# data isn't classified as GDPR Article 9 special-category data the way
# profile-service's biometric data is (revisit only if that classification
# is ever revised), so no per-user envelope encryption key is provisioned
# here. Adds the ElastiCache Redis wiring profile-service didn't need:
# diary-service reuses the single shared `module.elasticache` cluster
# (main.tf) via a `diary:*` key namespace (RedisDailySummaryCache) --
# same resolution as catalog-service's parallel-in-progress plan's
# Addendum 1 -- no new ElastiCache cluster provisioned here.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as
# identity-service.tf/profile-service.tf (see identity-service.tf's
# header comment for the full rationale).
#
# No JWT signing key, no internal-reveal-credential container, no KMS
# key: diary-service issues no tokens and exposes no internal,
# non-Kong-routed endpoint (unlike identity-service), and owns no
# per-user encryption key (unlike profile-service). Its only synchronous
# external dependency is identity-service's JWKS endpoint (ADR-0022),
# already resilience-configured in shared-contracts -- no new Terraform
# wiring needed for that.

locals {
  diary_service_name      = "diary-service"
  diary_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_diary_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.diary_service_name}"

  tags = merge(local.common_tags, {
    Service = local.diary_service_name
  })
}

# --- Secrets Manager: read the ARNs the platform-infra plan's `secrets`
# module already provisions for this service -- this file does not
# recreate any secret, only references the resulting names/ARNs to pass
# into the Helm release below. Only db-credentials (no JWT signing key
# entry, no internal-reveal-credential entry -- diary-service was never
# added to `var.jwt_signing_key_service_names`/
# `var.internal_reveal_credential_service_names`, only to
# `var.db_credential_service_names`, mirroring profile-service's own
# scoping).

locals {
  diary_service_db_credentials_secret_arn = module.secrets.db_credential_secret_arns[local.diary_service_name]
  diary_service_app_secrets_irsa_role_arn = module.secrets.app_secrets_irsa_role_arns[local.diary_service_name]
}

# --- Helm release ---
resource "helm_release" "diary_service" {
  name      = local.diary_service_name
  namespace = local.diary_service_namespace
  chart     = "${path.module}/../../../k8s/charts/diary-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by diary-service-ci.yml at
        # deploy time, never hardcoded in Terraform.
        repository = module.ecr_diary_service.repository_url
      }
      env = {
        AWS_REGION = var.aws_region
        # No auth token composed into this URL yet -- matches
        # modules/elasticache/main.tf's own documented gap ("this token
        # isn't yet in active use by any service"); revisit together with
        # that module once a service's caching need makes it worth
        # closing. A cache-layer outage (or an unauthenticated
        # connection being refused once auth is enforced) degrades to
        # "always read from Postgres" for the daily-summary query, per
        # RedisDailySummaryCache's documented fail-open posture -- never
        # service unavailability.
        DIARY_SERVICE_REDIS_URL = "redis://${module.elasticache.primary_endpoint_address}:${module.elasticache.port}/0"
      }
      secretsManager = {
        dbCredentials = local.diary_service_db_credentials_secret_arn
      }
      # values.yaml's serviceAccount.irsaRoleArn is the exact key
      # infra/k8s/charts/_lib/templates/_serviceaccount.tpl requires --
      # NOT nested under `annotations` (a prior mismatch here made
      # identity-service's chart fail its `required(...)` render guard
      # entirely, caught in that service's /implementation-review).
      serviceAccount = {
        irsaRoleArn = local.diary_service_app_secrets_irsa_role_arn
      }
      # _db-provision-job.tpl input (infra/k8s/charts/_lib) -- creates
      # this service's own logical database/role inside the shared RDS
      # instance at Helm-release time.
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.diary_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.diary_service_name]
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
    module.elasticache,
    module.secrets,
  ]
}
