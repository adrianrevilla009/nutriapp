# billing-service's Terraform footprint (implementation plan section 3):
# mirrors notification-service.tf's/catalog-service.tf's structure --
# narrowly wires this service's Helm release to the shared platform outputs
# (RDS instance endpoint, Secrets Manager entries) provisioned by the
# platform-infra plan, plus this service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as every other
# service.
#
# New secrets this file wires (via module.secrets, which this file does
# not itself provision -- only references the resulting ARNs):
#   - db-credentials (var.db_credential_service_names already includes
#     "billing-service", terraform.tfvars)
#   - internal-reveal-credential, for GET
#     /internal/v1/billing/entitlements/{user_id} (var.internal_reveal_credential_service_names
#     already includes "billing-service") -- same single-shared-credential,
#     no-caller-specific-grant design as identity-service/catalog-service,
#     not the newer cross_service_reveal_credentials per-caller mechanism:
#     there is no real caller yet (recipe-service/social-service/
#     analytics-service don't exist), so no caller-specific IRSA grant is
#     provisioned either -- a future consuming service's own implementation
#     plan adds a cross_service_reveal_credentials entry when it exists.
#   - stripe-api-key / stripe-webhook-signing-secret (new
#     stripe_api_key_service_names / stripe_webhook_signing_secret_service_names
#     variables, modules/secrets) -- both externally-issued, PENDING
#     placeholders until a real Stripe account exists (implementation plan
#     section 9, risk 2), same manual-population pattern as catalog-service's
#     USDA FDC key / food-recognition-service's Anthropic key.
#
# No new ElastiCache usage -- this plan has no caching requirement
# (implementation plan section 7).

locals {
  billing_service_name      = "billing-service"
  billing_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_billing_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.billing_service_name}"

  tags = merge(local.common_tags, {
    Service = local.billing_service_name
  })
}

# --- Secrets Manager: read the ARNs the platform-infra plan's `secrets`
# module already provisions for this service -- this file does not
# recreate any secret, only references the resulting names/ARNs to pass
# into the Helm release below.

locals {
  billing_service_db_credentials_secret_arn                = module.secrets.db_credential_secret_arns[local.billing_service_name]
  billing_service_internal_entitlement_credential_arn      = module.secrets.internal_reveal_credential_secret_arns[local.billing_service_name]
  billing_service_stripe_api_key_secret_arn                = module.secrets.stripe_api_key_secret_arns[local.billing_service_name]
  billing_service_stripe_webhook_signing_secret_secret_arn = module.secrets.stripe_webhook_signing_secret_secret_arns[local.billing_service_name]
  billing_service_app_secrets_irsa_role_arn                = module.secrets.app_secrets_irsa_role_arns[local.billing_service_name]
}

# --- Helm release ---
resource "helm_release" "billing_service" {
  name      = local.billing_service_name
  namespace = local.billing_service_namespace
  chart     = "${path.module}/../../../k8s/charts/billing-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by billing-service-ci.yml at
        # deploy time (`helm upgrade --set image.tag=$GIT_SHA`), never
        # hardcoded in Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_billing_service.repository_url
      }
      secretsManager = {
        dbCredentials                 = local.billing_service_db_credentials_secret_arn
        stripeApiKey                  = local.billing_service_stripe_api_key_secret_arn
        stripeWebhookSigningSecret    = local.billing_service_stripe_webhook_signing_secret_secret_arn
        internalEntitlementCredential = local.billing_service_internal_entitlement_credential_arn
      }
      serviceAccount = {
        irsaRoleArn = local.billing_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.billing_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.billing_service_name]
        image = {
          repository = module.ecr_db_provision.repository_url
          # tag intentionally omitted -- set by the shared
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

