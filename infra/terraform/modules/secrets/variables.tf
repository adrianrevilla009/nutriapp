# infra/terraform/modules/secrets/variables.tf
#
# Secrets Manager baseline + IRSA IAM policies (ADR-0007). Per-service
# database credentials are NOT generated here — this module only creates
# the addressable Secrets Manager *container* each service's
# `_db-provision-job` Helm hook writes into at deploy time (implementation
# plan section 9.1), plus the IAM roles that let that Job (write-only)
# and the service's own app pod (read-only) reach exactly that secret and
# nothing else.
#
# Naming convention every consuming service's Helm chart MUST match
# (documented again in infra/k8s/charts/_lib/README.md):
#   - DB-provisioning Job's ServiceAccount: "<service>-db-provision"
#   - Application pod's ServiceAccount:      "<service>"
# both in the single shared namespace (var.namespace).

variable "namespace" {
  description = "Kubernetes namespace every service's ServiceAccount lives in (single shared namespace convention, docs/containerization-and-orchestration.md section 3.3)."
  type        = string
  default     = "nutriapp-dev"
}

variable "environment" {
  type = string
}

variable "oidc_provider_arn" {
  description = "EKS cluster's IAM OIDC provider ARN (modules/eks output oidc_provider_arn)."
  type        = string
}

variable "oidc_provider_url" {
  description = "EKS cluster's IAM OIDC provider URL, including https:// (modules/eks output oidc_provider_url)."
  type        = string
}

variable "rds_master_user_secret_arn" {
  description = "Secrets Manager ARN of the shared RDS instance's master credential (modules/rds output master_user_secret_arn) — the db-provision-job IRSA role needs read access to this to connect as master and create its own database/role."
  type        = string
}

variable "jwt_signing_key_service_names" {
  description = "Service names that need a generated RSA JWT signing key pair stored in Secrets Manager (e.g. [\"identity-service\"])."
  type        = list(string)
  default     = []
}

variable "db_credential_service_names" {
  description = "Service names that need a Secrets Manager container for their own logical-database credentials, populated at deploy time by their _db-provision-job hook (e.g. [\"identity-service\"])."
  type        = list(string)
  default     = []
}

variable "internal_reveal_credential_service_names" {
  description = "Service names that need a generated shared bearer credential for an internal, non-Kong-routed service-to-service call (e.g. [\"identity-service\"] for the token-reveal endpoint notification-service authenticates against). Terraform-generated (random_password), never a literal value — same manual-rotation posture as the JWT signing key and DB credentials until volume justifies a custom rotation Lambda."
  type        = list(string)
  default     = []
}

variable "cross_service_reveal_credentials" {
  description = "Per-(owner_service, caller_service) pairs that need a DISTINCT, Terraform-generated (random_password) bearer credential for one service's internal, non-Kong-routed endpoint to be called by exactly one named other service -- e.g. [{owner_service = \"profile-service\", caller_service = \"nutrition-calculation-service\"}] for the reveal-metrics endpoint (profile-service implementation plan Addendum 2). Distinct from internal_reveal_credential_service_names above: that one is a single per-service secret with no caller-specific IRSA grant; this one creates both the secret AND a narrow IRSA role scoped to read exactly that secret, trusting only the named caller_service's ServiceAccount. Never share one entry's credential across a different caller."
  type = list(object({
    owner_service  = string
    caller_service = string
  }))
  default = []
}

variable "usda_fdc_api_key_service_names" {
  description = "Service names that need a Secrets Manager container for a third-party USDA FoodData Central API key (e.g. [\"catalog-service\"]). Unlike the JWT signing key/internal-reveal-credential above, this value cannot be Terraform-generated -- it is obtained externally (a free registered key from https://fdc.nal.usda.gov/api-key-signup.html) and written into the placeholder container manually, out-of-band, the same way _db-provision-job populates db_credentials at deploy time rather than Terraform apply time."
  type        = list(string)
  default     = []
}

variable "jwt_key_algorithm" {
  type    = string
  default = "RSA"
}

variable "jwt_key_rsa_bits" {
  type    = number
  default = 2048
}

variable "secrets_kms_key_id" {
  description = "Optional KMS key ARN for Secrets Manager secrets. null uses the default aws/secretsmanager key."
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
