# recipe-service's Terraform footprint (implementation plan section 3):
# mirrors billing-service.tf's/food-recognition-service.tf's structure --
# narrowly wires this service's Helm release to the shared platform outputs
# (RDS instance endpoint, Secrets Manager entries) provisioned by the
# platform-infra plan, plus this service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as every other
# service.
#
# This service is a CALLER of billing-service's internal, non-Kong-routed
# entitlement-check endpoint (GET /internal/v1/billing/entitlements/{user_id}).
#
# Resolved ambiguity (flagged in the final implementation report): the
# newer per-(owner_service, caller_service) `cross_service_reveal_credentials`
# mechanism (catalog-service/food-recognition-service's pairing) generates
# its OWN distinct random credential per pair -- it is NOT usable here,
# because billing-service's `internal_entitlement_routes.py` checks the
# caller's header against exactly one single value
# (`BILLING_INTERNAL_ENTITLEMENT_CREDENTIAL`, sourced from
# `internal_reveal_credential_secret_arns["billing-service"]`) -- the
# SAME single-shared-credential design billing-service.tf's own comment
# documents (identity-service/catalog-service precedent, "no
# caller-specific grant IAM policy exists for it anywhere in
# modules/secrets"). A new cross_service_reveal_credentials pair would
# mint a credential billing-service's route would simply reject (401).
# The correct integration is instead: grant recipe-service's own IRSA
# role read access to that SAME existing secret ARN, via a narrow inline
# policy (below) -- modules/secrets deliberately does not do this
# automatically for the single-shared-credential design, so this file
# provides it explicitly, exactly as billing-service.tf's own comment
# anticipated ("a future consuming service's own implementation plan
# adds ... when it exists").
#
# recipe-service exposes no internal, non-Kong-routed endpoint of its own
# in this plan's scope -- no internal_reveal_credential_service_names
# entry needed. It also calls catalog-service's PUBLIC
# GET /api/v1/catalog/products/{id} endpoint (no credential required,
# architecture-agent's confirmed design, implementation plan section 1).
#
# No new ElastiCache usage -- this plan has no caching requirement
# (implementation plan section 7: entitlement_cache IS the cache, Postgres).

locals {
  recipe_service_name      = "recipe-service"
  recipe_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_recipe_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.recipe_service_name}"

  tags = merge(local.common_tags, {
    Service = local.recipe_service_name
  })
}

# --- Secrets Manager: read the ARNs the `secrets` module already
# provisions for this service -- this file does not recreate any secret,
# only references the resulting names/ARNs.

locals {
  recipe_service_db_credentials_secret_arn = module.secrets.db_credential_secret_arns[local.recipe_service_name]
  recipe_service_app_secrets_irsa_role_arn = module.secrets.app_secrets_irsa_role_arns[local.recipe_service_name]
  recipe_service_app_secrets_irsa_role_name = regex(
    "role/(.+)$",
    local.recipe_service_app_secrets_irsa_role_arn,
  )[0]
  # NEW, narrow exception: reads billing-service's OWN single shared
  # internal-reveal credential ARN -- exactly this ARN, never
  # billing-service's db-credentials or its Stripe secrets. See the
  # comment block above for why this is the correct ARN (not a new
  # cross_service_reveal_credentials pair).
  recipe_service_billing_entitlement_credential_arn = module.secrets.internal_reveal_credential_secret_arns["billing-service"]
}

# Separate, narrowly-scoped inline policy -- not folded into the general
# app_secrets policy document -- granting read on exactly billing-service's
# single internal-reveal credential ARN above (not this service's own
# secret). Attached to the SAME role this service's pod already assumes
# (one ServiceAccount, one IRSA role).
resource "aws_iam_role_policy" "recipe_service_billing_entitlement_credential_read" {
  name = "billing-entitlement-credential-read"
  role = local.recipe_service_app_secrets_irsa_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadBillingServiceInternalRevealCredential"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = local.recipe_service_billing_entitlement_credential_arn
    }]
  })
}

# --- Helm release ---
resource "helm_release" "recipe_service" {
  name      = local.recipe_service_name
  namespace = local.recipe_service_namespace
  chart     = "${path.module}/../../../k8s/charts/recipe-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by recipe-service-ci.yml at
        # deploy time (`helm upgrade --set image.tag=$GIT_SHA`), never
        # hardcoded in Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_recipe_service.repository_url
      }
      secretsManager = {
        dbCredentials                = local.recipe_service_db_credentials_secret_arn
        billingEntitlementCredential = local.recipe_service_billing_entitlement_credential_arn
      }
      serviceAccount = {
        irsaRoleArn = local.recipe_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.recipe_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.recipe_service_name]
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
