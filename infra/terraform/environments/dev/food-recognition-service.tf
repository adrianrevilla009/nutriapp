# food-recognition-service's Terraform footprint (implementation plan
# section 3/7): mirrors nutrition-calculation-service.tf's structure --
# narrowly wires this service's Helm release to the shared platform
# outputs (RDS instance endpoint, Secrets Manager entries) provisioned by
# the platform-infra plan, plus this service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as every other
# service.
#
# No JWT signing key, no own internal-reveal-credential container: this
# service issues no tokens and exposes no internal, non-Kong-routed
# endpoint of its own. It DOES need read access to two secrets it does
# not own outright:
#   1. Its own metered ANTHROPIC_API_KEY container (a placeholder this
#      file provisions via anthropic_api_key_service_names, populated
#      manually out-of-band with a real Anthropic Console key, same
#      shape as catalog-service's USDA FDC key).
#   2. catalog-service's per-caller internal-lookup credential
#      (implementation plan section 6(c)) -- provisioned by
#      modules/secrets' `cross_service_reveal_credentials` mechanism
#      (catalog-service implementation plan Addendum 2), this file only
#      consumes the resulting `cross_service_reveal_credential_secret_arns`
#      output, it does not (re)define the secret itself.
#
# No new ElastiCache usage -- this plan has no caching requirement.

locals {
  food_recognition_service_name      = "food-recognition-service"
  food_recognition_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_food_recognition_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.food_recognition_service_name}"

  tags = merge(local.common_tags, {
    Service = local.food_recognition_service_name
  })
}

# --- Secrets Manager: read the ARNs the `secrets` module already
# provisions for this service -- this file does not recreate any secret,
# only references the resulting names/ARNs.

locals {
  food_recognition_service_db_credentials_secret_arn    = module.secrets.db_credential_secret_arns[local.food_recognition_service_name]
  food_recognition_service_anthropic_api_key_secret_arn = module.secrets.anthropic_api_key_secret_arns[local.food_recognition_service_name]
  food_recognition_service_app_secrets_irsa_role_arn    = module.secrets.app_secrets_irsa_role_arns[local.food_recognition_service_name]
  food_recognition_service_app_secrets_irsa_role_name = regex(
    "role/(.+)$",
    local.food_recognition_service_app_secrets_irsa_role_arn,
  )[0]
  # NEW, narrow exception (implementation plan section 6(c)): exactly this
  # ARN, never catalog-service's db-credentials or its other secrets --
  # see catalog-service.tf for the owning side of this same pairing (added
  # via that service's Addendum 2 sub-plan, in a parallel worktree).
  food_recognition_service_catalog_lookup_credential_arn = module.secrets.cross_service_reveal_credential_secret_arns["catalog-service-food-recognition-service"]
}

# Separate, narrowly-scoped inline policy -- not folded into the general
# app_secrets policy document -- granting read on exactly the one
# cross_service_reveal_credential ARN above. Attached to the SAME role
# this service's pod already assumes (one ServiceAccount, one IRSA role).
resource "aws_iam_role_policy" "food_recognition_service_catalog_lookup_credential_read" {
  name = "catalog-lookup-credential-read"
  role = local.food_recognition_service_app_secrets_irsa_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadExactlyOneCrossServiceRevealCredential"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = local.food_recognition_service_catalog_lookup_credential_arn
    }]
  })
}

# --- Helm release ---
resource "helm_release" "food_recognition_service" {
  name      = local.food_recognition_service_name
  namespace = local.food_recognition_service_namespace
  chart     = "${path.module}/../../../k8s/charts/food-recognition-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by
        # food-recognition-service-ci.yml at deploy time (`helm upgrade
        # --set image.tag=$GIT_SHA`), never hardcoded in Terraform, per
        # ci-cd-conventions SKILL.md.
        repository = module.ecr_food_recognition_service.repository_url
      }
      secretsManager = {
        dbCredentials           = local.food_recognition_service_db_credentials_secret_arn
        anthropicApiKey         = local.food_recognition_service_anthropic_api_key_secret_arn
        catalogLookupCredential = local.food_recognition_service_catalog_lookup_credential_arn
      }
      serviceAccount = {
        irsaRoleArn = local.food_recognition_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.food_recognition_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.food_recognition_service_name]
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
