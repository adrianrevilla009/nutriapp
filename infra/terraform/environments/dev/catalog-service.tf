# catalog-service's Terraform footprint (implementation plan section 7):
# mirrors identity-service.tf/profile-service.tf's structure -- narrowly
# wires this service's Helm release to the shared platform outputs (RDS
# instance endpoint, Secrets Manager entries) provisioned by the
# companion platform-infra plan, plus this service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as
# identity-service.tf/profile-service.tf (see identity-service.tf's
# header comment for the full rationale).
#
# No JWT signing key: catalog-service issues no tokens. It does now
# expose one internal, non-Kong-routed endpoint (`GET
# /internal/v1/catalog/lookup`, implementation plan Addendum 2) --
# verified against a distinct, per-caller credential (food-recognition-
# service only), via the same `cross_service_reveal_credential` module
# mechanism profile-service's Addendum 2 introduced, not the generic
# `internal_reveal_credential` shape identity-service uses. It does need
# one new secret container this module didn't previously have -- a
# third-party USDA FoodData Central API key
# (`usda_fdc_api_key_service_names`, added to
# infra/terraform/modules/secrets/ as a follow-up, human-approved
# reconciliation step, following the same per-service-container pattern
# as db-credentials/internal-reveal-credential). Unlike those two, this
# value cannot be Terraform-generated -- it is a real key registered at
# https://fdc.nal.usda.gov/api-key-signup.html and written into the
# placeholder container manually, out-of-band, before any real (i.e. not
# DEMO_KEY smoke-test) ingestion run.
#
# Redis: reuses the single shared infra/terraform/modules/elasticache
# cluster the platform-infra plan already provisions, isolated purely by
# a `catalog:*` key namespace -- no new ElastiCache cluster is
# provisioned (implementation plan Addendum 1, section 9.7). The full
# `CATALOG_SERVICE_REDIS_URL` (host + TLS + the cluster's Terraform-
# generated `auth_token`, module.elasticache.auth_token_secret_arn) is
# NOT wired into this Helm release yet -- identity-service.tf, the
# structural precedent for this file, has the same gap despite
# identity-service also depending on Redis (its rate limiter). Assembling
# an authenticated `rediss://` URL from two separate Secrets Manager
# entries (host/port are plain Terraform outputs, the auth token is a
# secret) needs either ExternalSecret templating or an
# application-side "read host+port from env, auth token from its own
# secret" split that neither this service's `Settings.from_env()` nor
# identity-service's supports today. Flagged here explicitly rather than
# silently left as a gap: a real (non-docker-compose) deployment of this
# chart will fail to reach Redis until this is resolved -- a follow-up
# for whoever executes platform-infra's next reconciliation pass, not
# something to paper over with an unauthenticated URL that would not
# actually work against `transit_encryption_enabled = true`.

locals {
  catalog_service_name      = "catalog-service"
  catalog_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_catalog_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.catalog_service_name}"

  tags = merge(local.common_tags, {
    Service = local.catalog_service_name
  })
}

# --- Secrets Manager: read the ARNs the platform-infra plan's `secrets`
# module already provisions for this service -- this file does not
# recreate any secret, only references the resulting names/ARNs to pass
# into the Helm release below.

locals {
  catalog_service_db_credentials_secret_arn   = module.secrets.db_credential_secret_arns[local.catalog_service_name]
  catalog_service_usda_fdc_api_key_secret_arn = module.secrets.usda_fdc_api_key_secret_arns[local.catalog_service_name]
  catalog_service_app_secrets_irsa_role_arn   = module.secrets.app_secrets_irsa_role_arns[local.catalog_service_name]
  # implementation plan Addendum 2: the internal lookup endpoint's
  # distinct, per-caller credential -- keyed "<owner_service>-<caller_service>"
  # per modules/secrets' cross_service_reveal_credential_secret_arns output.
  catalog_service_lookup_credential_food_recognition_arn = module.secrets.cross_service_reveal_credential_secret_arns["${local.catalog_service_name}-food-recognition-service"]
}

# --- Helm release ---
resource "helm_release" "catalog_service" {
  name      = local.catalog_service_name
  namespace = local.catalog_service_namespace
  chart     = "${path.module}/../../../k8s/charts/catalog-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by catalog-service-ci.yml at
        # deploy time (`helm upgrade --set image.tag=$GIT_SHA`), never
        # hardcoded in Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_catalog_service.repository_url
      }
      env = {
        RDS_HOST = module.rds.db_instance_address
        RDS_PORT = module.rds.db_instance_port
      }
      secretsManager = {
        dbCredentials            = local.catalog_service_db_credentials_secret_arn
        usdaFdcApiKey            = local.catalog_service_usda_fdc_api_key_secret_arn
        internalLookupCredential = local.catalog_service_lookup_credential_food_recognition_arn
      }
      serviceAccount = {
        irsaRoleArn = local.catalog_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.catalog_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.catalog_service_name]
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
