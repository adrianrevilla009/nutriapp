# notification-service's Terraform footprint (implementation plan
# section 3/7): mirrors nutrition-calculation-service.tf's structure --
# narrowly wires this service's Helm release to the shared platform
# outputs (RDS instance endpoint, Secrets Manager entries) provisioned by
# the platform-infra plan, plus this service's own ECR repository.
#
# Deliberately does NOT create the service's database via Terraform
# directly -- same _db-provision-job Helm-hook pattern as every other
# service.
#
# No JWT signing key, no OWN internal-reveal-credential container: this
# service issues no tokens and exposes no internal, non-Kong-routed
# endpoint of its own beyond the SES/SNS bounce-webhook route (which
# needs no Terraform-provisioned credential today). It DOES need read
# access to a secret it does not own -- identity-service's existing,
# SINGLE, shared internal-reveal credential
# (`module.secrets.internal_reveal_credential_secret_arns["identity-service"]`,
# `internal_reveal_credential_service_names` already includes
# "identity-service"). This is deliberately NOT the newer
# `cross_service_reveal_credentials` per-caller mechanism catalog-
# service/food-recognition-service and profile-service/nutrition-
# calculation-service use -- identity-service's reveal endpoint predates
# that mechanism and keeps its existing single-shared-credential design
# (docs/api-catalog.md's explicit note on this distinction). See
# services/notification-service/infrastructure/composition_root.py's
# Settings docstring for the same rationale on the application side.
#
# SES/SNS (ADR-0011): a real SES sending identity + configuration set are
# provisioned below (sandbox mode -- no production-sending access
# requested here, that is a separately tracked AWS lead-time item per
# ADR-0011 and implementation plan section 9, risk 1). SNS platform
# application (real push-provider registration) is deliberately NOT
# provisioned yet -- no mobile client exists (ADR-0014), so there is
# nothing to register against; implementation plan section 9.3.
#
# No new ElastiCache usage -- this plan has no caching requirement
# (implementation plan section 7).

locals {
  notification_service_name      = "notification-service"
  notification_service_namespace = "nutriapp-dev"
}

# --- ECR: this service's own app image ---
module "ecr_notification_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.notification_service_name}"

  tags = merge(local.common_tags, {
    Service = local.notification_service_name
  })
}

# --- SES: sandbox sending identity + configuration set (implementation
# plan section 3). Sandbox mode is SES's default for a new identity/
# account until production access is explicitly requested (tracked
# separately, ADR-0011) -- no `aws_ses_domain_identity` verification
# record management or DKIM setup is provisioned here, since that is
# meaningless before production access exists.
resource "aws_ses_email_identity" "notification_service_sandbox_sender" {
  email = "no-reply@nutriapp.example"
}

resource "aws_sesv2_configuration_set" "notification_service" {
  configuration_set_name = "${local.notification_service_name}-${var.environment}"

  reputation_options {
    reputation_metrics_enabled = true
  }

  delivery_options {
    tls_policy = "REQUIRE"
  }
}

# --- Secrets Manager: read the ARNs the `secrets` module already
# provisions -- this file does not recreate identity-service's reveal
# credential, only references the resulting name/ARN. It DOES own a new,
# service-local secret holding the SES/SNS sandbox endpoint config the
# httpx-based adapters (infrastructure/external/ses_email_adapter.py,
# sns_push_adapter.py) call -- not a third-party credential, so it is
# defined directly here rather than via the shared `secrets` module's
# generic mechanisms, none of which fit a "two related config URLs"
# shape.

locals {
  notification_service_db_credentials_secret_arn = module.secrets.db_credential_secret_arns[local.notification_service_name]
  notification_service_app_secrets_irsa_role_arn = module.secrets.app_secrets_irsa_role_arns[local.notification_service_name]
  notification_service_app_secrets_irsa_role_name = regex(
    "role/(.+)$",
    local.notification_service_app_secrets_irsa_role_arn,
  )[0]
  # NEW, narrow exception: exactly this ARN, never identity-service's
  # db-credentials, JWT signing key, or any other secret.
  notification_service_identity_reveal_credential_arn = module.secrets.internal_reveal_credential_secret_arns["identity-service"]
}

resource "aws_secretsmanager_secret" "notification_service_ses_endpoint" {
  # checkov:skip=CKV2_AWS_57:Sandbox-mode endpoint config, not a rotatable credential -- same manual-rotation posture as every other application-defined config container in this file until volume justifies a custom rotation Lambda.
  name = "nutriapp/${var.environment}/${local.notification_service_name}/ses-endpoint"

  tags = merge(local.common_tags, {
    Service = local.notification_service_name
  })
}

resource "aws_secretsmanager_secret_version" "notification_service_ses_endpoint" {
  secret_id = aws_secretsmanager_secret.notification_service_ses_endpoint.id
  secret_string = jsonencode({
    # Local-fake/sandbox endpoints only (docs/notifications.md section 5)
    # -- never real SES/SNS regional endpoints until production access
    # (ADR-0011) is granted and this value is updated out-of-band.
    ses_base_url = "http://ses-fake.${local.notification_service_namespace}.svc.cluster.local:9001"
    sns_base_url = "http://sns-fake.${local.notification_service_namespace}.svc.cluster.local:9002"
  })
}

# Separate, narrowly-scoped inline policy -- not folded into the general
# app_secrets policy document -- granting read on exactly the one
# internal_reveal_credential ARN above. Attached to the SAME role this
# service's pod already assumes (one ServiceAccount, one IRSA role).
resource "aws_iam_role_policy" "notification_service_identity_reveal_credential_read" {
  name = "identity-reveal-credential-read"
  role = local.notification_service_app_secrets_irsa_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadIdentityServiceInternalRevealCredential"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = local.notification_service_identity_reveal_credential_arn
    }]
  })
}

# --- Helm release ---
resource "helm_release" "notification_service" {
  name      = local.notification_service_name
  namespace = local.notification_service_namespace
  chart     = "${path.module}/../../../k8s/charts/notification-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by
        # notification-service-ci.yml at deploy time (`helm upgrade
        # --set image.tag=$GIT_SHA`), never hardcoded in Terraform, per
        # ci-cd-conventions SKILL.md.
        repository = module.ecr_notification_service.repository_url
      }
      secretsManager = {
        dbCredentials            = local.notification_service_db_credentials_secret_arn
        identityRevealCredential = local.notification_service_identity_reveal_credential_arn
        sesEndpoint              = aws_secretsmanager_secret.notification_service_ses_endpoint.arn
      }
      serviceAccount = {
        irsaRoleArn = local.notification_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.notification_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.notification_service_name]
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

