# nutrition-assistant-service's Terraform footprint (implementation plan
# section 3): mirrors analytics-service.tf's structure -- narrowly wires
# this service's Helm release to the shared platform outputs (RDS
# instance endpoint, Secrets Manager entries, and -- NEW, first time any
# service needs this -- module.qdrant's shared Qdrant instance) plus this
# service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as every other
# service.
#
# This service is a CALLER of billing-service's internal, non-Kong-routed
# entitlement-check endpoint (GET /internal/v1/billing/entitlements/{user_id}),
# same integration recipe-service.tf/social-service.tf/analytics-service.tf
# already document.
#
# This service ALSO needs its own metered ANTHROPIC_API_KEY container
# (ClaudeConversationAdapter, implementation plan section 4/9 resolution
# 5) -- same anthropic_api_key_service_names mechanism food-recognition-service.tf
# already uses, a SEPARATE container/ARN from that service's own key
# (never shared between the two services, per modules/secrets' per-service
# map).
#
# No new ElastiCache usage -- no Redis caching requirement this pass
# (implementation plan section 7: a Redis cache-aside layer for
# non-user-specific repeated questions is a should-build-if-time-allows
# item, not built this pass).
#
# No embedding-vendor secret needed -- LocalEmbeddingAdapter is
# self-hosted, no external API key (implementation plan section 9
# resolution 1).

locals {
  nutrition_assistant_service_name      = "nutrition-assistant-service"
  nutrition_assistant_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_nutrition_assistant_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.nutrition_assistant_service_name}"

  tags = merge(local.common_tags, {
    Service = local.nutrition_assistant_service_name
  })
}

# --- Secrets Manager: read the ARNs the `secrets` module already
# provisions for this service -- this file does not recreate any secret,
# only references the resulting names/ARNs.

locals {
  nutrition_assistant_service_db_credentials_secret_arn    = module.secrets.db_credential_secret_arns[local.nutrition_assistant_service_name]
  nutrition_assistant_service_anthropic_api_key_secret_arn = module.secrets.anthropic_api_key_secret_arns[local.nutrition_assistant_service_name]
  nutrition_assistant_service_app_secrets_irsa_role_arn    = module.secrets.app_secrets_irsa_role_arns[local.nutrition_assistant_service_name]
  nutrition_assistant_service_app_secrets_irsa_role_name = regex(
    "role/(.+)$",
    local.nutrition_assistant_service_app_secrets_irsa_role_arn,
  )[0]
  # Reads billing-service's OWN single shared internal-reveal credential
  # ARN -- exactly this ARN, never billing-service's db-credentials or its
  # Stripe secrets. Mirrors recipe-service.tf's/social-service.tf's/
  # analytics-service.tf's identical grant.
  nutrition_assistant_service_billing_entitlement_credential_arn = module.secrets.internal_reveal_credential_secret_arns["billing-service"]
}

# Separate, narrowly-scoped inline policy -- not folded into the general
# app_secrets policy document -- granting read on exactly billing-service's
# single internal-reveal credential ARN above (not this service's own
# secret). Attached to the SAME role this service's pod already assumes
# (one ServiceAccount, one IRSA role).
resource "aws_iam_role_policy" "nutrition_assistant_service_billing_entitlement_credential_read" {
  name = "billing-entitlement-credential-read"
  role = local.nutrition_assistant_service_app_secrets_irsa_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadBillingServiceInternalRevealCredential"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = local.nutrition_assistant_service_billing_entitlement_credential_arn
    }]
  })
}

# --- Helm release ---
resource "helm_release" "nutrition_assistant_service" {
  name      = local.nutrition_assistant_service_name
  namespace = local.nutrition_assistant_service_namespace
  chart     = "${path.module}/../../../k8s/charts/nutrition-assistant-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by
        # nutrition-assistant-service-ci.yml at deploy time
        # (`helm upgrade --set image.tag=$GIT_SHA`), never hardcoded in
        # Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_nutrition_assistant_service.repository_url
      }
      secretsManager = {
        dbCredentials                = local.nutrition_assistant_service_db_credentials_secret_arn
        anthropicApiKey              = local.nutrition_assistant_service_anthropic_api_key_secret_arn
        billingEntitlementCredential = local.nutrition_assistant_service_billing_entitlement_credential_arn
      }
      serviceAccount = {
        irsaRoleArn = local.nutrition_assistant_service_app_secrets_irsa_role_arn
      }
      env = {
        qdrantUrl = module.qdrant.qdrant_url
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.nutrition_assistant_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.nutrition_assistant_service_name]
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
    module.qdrant,
  ]
}
