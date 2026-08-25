# profile-service's Terraform footprint (implementation plan section 7):
# mirrors identity-service.tf's structure -- narrowly wires this service's
# Helm release to the shared platform outputs (RDS instance endpoint,
# Secrets Manager db-credentials container) provisioned by the companion
# platform-infra plan, plus this service's own ECR repository and its own
# AWS KMS key for per-user envelope encryption (implementation plan
# Addendum 1 -- profile-service owns its key material, not a shared/
# centralized store).
#
# Deliberately does NOT create the service's database via Terraform directly
# -- same _db-provision-job Helm-hook pattern as identity-service.tf (see
# that file's header comment for the full rationale).
#
# No JWT signing key, no internal-reveal-credential container:
# profile-service issues no tokens and exposes no internal, non-Kong-routed
# endpoint (unlike identity-service). Its only synchronous external
# dependency is AWS KMS, granted via IRSA (IAM), not a Secrets Manager
# entry.

locals {
  profile_service_name      = "profile-service"
  profile_service_namespace = "nutriapp-dev"
  # Reconstructs module.secrets' internal naming convention
  # ("nutriapp-${environment}-${service}-app-secrets", modules/secrets/main.tf)
  # since that module only outputs the role ARN, not its bare name --
  # needed here to attach an additional (KMS) policy to the same role.
  profile_service_app_secrets_role_name = "nutriapp-${var.environment}-${local.profile_service_name}-app-secrets"
}

# --- ECR: this service's own app image ---
module "ecr_profile_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.profile_service_name}"

  tags = merge(local.common_tags, {
    Service = local.profile_service_name
  })
}

# --- AWS KMS: per-user envelope-encryption key (implementation plan
# Addendum 1) --- profile-service's own CMK, used only to
# GenerateDataKey/Decrypt per-user Data Encryption Keys
# (infrastructure/security/kms_envelope_data_encryption.py) -- the actual
# field-level AES-256-GCM encryption happens locally in the app, never a
# per-field KMS call.
resource "aws_kms_key" "profile_service_data_key" {
  description             = "profile-service per-user envelope-encryption key (biometric/health data, GDPR Art. 9)"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(local.common_tags, {
    Service = local.profile_service_name
  })
}

resource "aws_kms_alias" "profile_service_data_key" {
  name          = "alias/nutriapp-${var.environment}-${local.profile_service_name}-data-key"
  target_key_id = aws_kms_key.profile_service_data_key.key_id
}

# Grants this service's app ServiceAccount (via the IRSA role module.secrets
# already created for its Secrets Manager access) permission to call
# GenerateDataKey/Decrypt against exactly this key -- least privilege, no
# other service can use profile-service's data key.
data "aws_iam_policy_document" "profile_service_kms_access" {
  statement {
    sid    = "UsePerUserEnvelopeEncryptionKey"
    effect = "Allow"
    actions = [
      "kms:GenerateDataKey",
      "kms:Decrypt",
    ]
    resources = [aws_kms_key.profile_service_data_key.arn]
  }
}

resource "aws_iam_role_policy" "profile_service_kms_access" {
  name   = "kms-envelope-encryption"
  role   = local.profile_service_app_secrets_role_name
  policy = data.aws_iam_policy_document.profile_service_kms_access.json

  depends_on = [module.secrets]
}

# --- Secrets Manager: read the ARNs the platform-infra plan's `secrets`
# module already provisions for this service (db-credentials container
# only -- see file header) ---

locals {
  profile_service_db_credentials_secret_arn = module.secrets.db_credential_secret_arns[local.profile_service_name]
  profile_service_app_secrets_irsa_role_arn = module.secrets.app_secrets_irsa_role_arns[local.profile_service_name]
}

# --- Helm release ---
resource "helm_release" "profile_service" {
  name      = local.profile_service_name
  namespace = local.profile_service_namespace
  chart     = "${path.module}/../../../k8s/charts/profile-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by profile-service-ci.yml at
        # deploy time, never hardcoded in Terraform.
        repository = module.ecr_profile_service.repository_url
      }
      env = {
        AWS_REGION                 = var.aws_region
        PROFILE_SERVICE_KMS_KEY_ID = aws_kms_key.profile_service_data_key.key_id
      }
      secretsManager = {
        dbCredentials = local.profile_service_db_credentials_secret_arn
      }
      serviceAccount = {
        irsaRoleArn = local.profile_service_app_secrets_irsa_role_arn
      }
      dbProvision = {
        rdsHost               = module.rds.db_instance_address
        rdsMasterSecretArn    = module.rds.master_user_secret_arn
        dbCredentialSecretArn = local.profile_service_db_credentials_secret_arn
        irsaRoleArn           = module.secrets.db_provision_irsa_role_arns[local.profile_service_name]
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
    aws_iam_role_policy.profile_service_kms_access,
  ]
}
