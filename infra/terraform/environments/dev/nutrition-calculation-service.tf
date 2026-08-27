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
# (implementation plan Addendum 1, security sub-addendum requirements 1/2).
#
# That secret is provisioned by modules/secrets' `cross_service_reveal_credentials`
# mechanism, owned by profile-service's coordinated reveal-endpoint
# sub-plan (profile-service implementation-plan Addendum 2) -- this file
# only consumes the resulting `cross_service_reveal_credential_secret_arns`
# output, it does not (re)define the secret itself. Reconciled at
# /implementation-review (Addendum 1 item 12) after two independently-built
# worktrees briefly diverged on how this grant should be shaped.
#
# Grant shape: profile-service's module addition also creates a dedicated
# `cross_service_reveal_credential_caller` IAM role trusting only this
# service's ServiceAccount -- but a K8s ServiceAccount can only carry one
# `eks.amazonaws.com/role-arn` IRSA annotation, and this service's
# ServiceAccount already needs its own `app_secrets` role for its own
# db-credentials. So instead of assuming that second role, this file
# attaches ONE additional, separately-auditable inline policy directly to
# this service's *existing* `app_secrets` role, scoped to exactly the one
# `cross_service_reveal_credential` ARN below -- never profile-service's
# db-credentials or KMS key (the narrow, human-approved exception to
# CLAUDE.md section 2.9 stays exactly as narrow as originally approved,
# just attached via a different, equally-scoped mechanism).
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
  nutrition_calculation_service_app_secrets_irsa_role_name = regex(
    "role/(.+)$",
    local.nutrition_calculation_service_app_secrets_irsa_role_arn,
  )[0]
  # NEW, narrow exception (Addendum 1 security sub-addendum requirement 2):
  # exactly this ARN, never profile-service's db-credentials or KMS key --
  # see profile-service.tf for the owning side of this same pairing.
  nutrition_calculation_service_profile_reveal_credential_arn = module.secrets.cross_service_reveal_credential_secret_arns["profile-service-nutrition-calculation-service"]
}

# Separate, narrowly-scoped inline policy -- not folded into the general
# app_secrets policy document -- granting read on exactly the one
# cross_service_reveal_credential ARN above. Attached to the SAME role
# this service's pod already assumes (see the header comment for why: one
# ServiceAccount, one IRSA role).
resource "aws_iam_role_policy" "nutrition_calculation_service_profile_reveal_credential_read" {
  name = "profile-reveal-credential-read"
  role = local.nutrition_calculation_service_app_secrets_irsa_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadExactlyOneCrossServiceRevealCredential"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = local.nutrition_calculation_service_profile_reveal_credential_arn
    }]
  })
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
