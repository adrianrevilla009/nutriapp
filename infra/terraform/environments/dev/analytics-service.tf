# analytics-service's Terraform footprint (implementation plan section 3):
# mirrors social-service.tf's structure -- narrowly wires this service's
# Helm release to the shared platform outputs (RDS instance endpoint,
# Secrets Manager entries) provisioned by the platform-infra plan, plus
# this service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as every other
# service.
#
# This service is a CALLER of billing-service's internal, non-Kong-routed
# entitlement-check endpoint (GET /internal/v1/billing/entitlements/{user_id}),
# same integration recipe-service.tf/social-service.tf already document --
# see those files' header comments for the full reasoning on why the
# single-shared-credential design (not the newer per-caller
# cross_service_reveal_credentials mechanism) is the correct one to reuse
# here too.
#
# analytics-service exposes no internal, non-Kong-routed endpoint of its
# own in this plan's scope -- no internal_reveal_credential_service_names
# entry needed. It makes no synchronous call to diary-service,
# profile-service, nutrition-calculation-service, or notification-service
# at all -- all four are consumed entirely asynchronously via RabbitMQ, so
# unlike recipe-service.tf there is no second external-service IAM grant
# here beyond the billing-service entitlement credential.
#
# No new ElastiCache usage -- this plan has no Redis caching requirement
# (implementation plan section 7: entitlement_cache/daily_log_summary/
# micronutrient_window ARE the cache/projection, Postgres).

locals {
  analytics_service_name      = "analytics-service"
  analytics_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_analytics_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.analytics_service_name}"

  tags = merge(local.common_tags, {
    Service = local.analytics_service_name
  })
}

# --- Secrets Manager: read the ARNs the `secrets` module already
# provisions for this service -- this file does not recreate any secret,
# only references the resulting names/ARNs.

locals {
  analytics_service_db_credentials_secret_arn = module.secrets.db_credential_secret_arns[local.analytics_service_name]
  analytics_service_app_secrets_irsa_role_arn = module.secrets.app_secrets_irsa_role_arns[local.analytics_service_name]
  analytics_service_app_secrets_irsa_role_name = regex(
    "role/(.+)$",
    local.analytics_service_app_secrets_irsa_role_arn,
  )[0]
  # Reads billing-service's OWN single shared internal-reveal credential
  # ARN -- exactly this ARN, never billing-service's db-credentials or its
  # Stripe secrets. Mirrors recipe-service.tf's/social-service.tf's
  # identical grant.
  analytics_service_billing_entitlement_credential_arn = module.secrets.internal_reveal_credential_secret_arns["billing-service"]
}

# Separate, narrowly-scoped inline policy -- not folded into the general
# app_secrets policy document -- granting read on exactly billing-service's
# single internal-reveal credential ARN above (not this service's own
# secret). Attached to the SAME role this service's pod already assumes
# (one ServiceAccount, one IRSA role).
resource "aws_iam_role_policy" "analytics_service_billing_entitlement_credential_read" {
  name = "billing-entitlement-credential-read"
  role = local.analytics_service_app_secrets_irsa_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadBillingServiceInternalRevealCredential"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = local.analytics_service_billing_entitlement_credential_arn
    }]
  })
}

# --- Helm release ---
resource "helm_release" "analytics_service" {
  name      = local.analytics_service_name
  namespace = local.analytics_service_namespace
  chart     = "${path.module}/../../../k8s/charts/analytics-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by analytics-service-ci.yml at
        # deploy time (`helm upgrade --set image.tag=$GIT_SHA`), never
        # hardcoded in Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_analytics_service.repository_url
      }
      secretsManager = {
        dbCredentials                = local.analytics_service_db_credentials_secret_arn
        billingEntitlementCredential = local.analytics_service_billing_entitlement_credential_arn
      }
      serviceAccount = {
        irsaRoleArn = local.analytics_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.analytics_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.analytics_service_name]
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
