# infra/terraform/environments/dev/variables.tf
#
# Thin environment composition: only variables/sizing live here, per
# .claude/skills/terraform-conventions/SKILL.md. No hardcoded account IDs
# or CIDRs baked into modules — this is where env-specific values are
# actually supplied.

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.0.0/24", "10.20.1.0/24", "10.20.2.0/24"]
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.10.0/24", "10.20.11.0/24", "10.20.12.0/24"]
}

variable "cluster_name" {
  type    = string
  default = "nutriapp-dev"
}

variable "kubernetes_version" {
  type    = string
  default = "1.32"
}

variable "cluster_endpoint_public_access_cidrs" {
  description = <<-EOT
    CIDR blocks allowed to reach the EKS public API endpoint (resolved
    decision, implementation plan section 9.3). The placeholder below
    (TEST-NET-3, RFC 5737 documentation range — never routable) MUST be
    overridden with the operator's real, current public IP before a real
    apply, ideally via a gitignored terraform.tfvars.local rather than
    editing this committed file, since a real IP is operator-identifying.
  EOT
  type        = list(string)
  default     = ["203.0.113.0/32"]
}

variable "namespace" {
  type    = string
  default = "nutriapp-dev"
}

# --- RDS ---

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "rds_allocated_storage" {
  type    = number
  default = 20
}

variable "rds_multi_az" {
  type    = bool
  default = false
}

# --- ElastiCache ---

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

# --- Secrets (this plan provisions identity-service's containers only;
# see infra/k8s/charts/identity-service/ (owned by identity-service's own
# plan) for the Helm release that populates/consumes them) ---

variable "jwt_signing_key_service_names" {
  type    = list(string)
  default = ["identity-service"]
}

variable "db_credential_service_names" {
  type = list(string)
  default = [
    "identity-service",
    "profile-service",
    "catalog-service",
    "nutrition-calculation-service",
    "food-recognition-service",
  ]
}

variable "internal_reveal_credential_service_names" {
  type    = list(string)
  default = ["identity-service"]
}

# NOTE: this block previously existed twice in this file (a duplicate
# `variable "cross_service_reveal_credentials"` block -- an artifact of
# two independently-developed worktrees, nutrition-calculation-service's
# and profile-service's Addendum 2, each adding their own copy without the
# other's entry). Terraform rejects a duplicate variable declaration
# outright, so this file was never actually apply-able as committed;
# reconciled here into one block carrying every pair, per this session's
# addition of the catalog-service/food-recognition-service pair
# (implementation plan section 6(c)).
variable "cross_service_reveal_credentials" {
  description = "Per-(owner_service, caller_service) pairs needing a distinct internal reveal credential + narrow caller IRSA grant (see modules/secrets/variables.tf's fuller description). profile-service's reveal-metrics endpoint, called only by nutrition-calculation-service (profile-service implementation plan Addendum 2 / nutrition-calculation-service implementation plan Addendum 1); catalog-service's internal barcode-lookup endpoint, called only by food-recognition-service (catalog-service implementation plan Addendum 2 / food-recognition-service implementation plan section 6(c))."
  type = list(object({
    owner_service  = string
    caller_service = string
  }))
  default = [
    { owner_service = "profile-service", caller_service = "nutrition-calculation-service" },
    { owner_service = "catalog-service", caller_service = "food-recognition-service" },
  ]
}

variable "usda_fdc_api_key_service_names" {
  type    = list(string)
  default = ["catalog-service"]
}

variable "anthropic_api_key_service_names" {
  description = "Service names that need a Secrets Manager container for a metered, third-party Anthropic API key (food-recognition-service implementation plan section 6(b)). Same externally-issued-secret shape as usda_fdc_api_key_service_names -- cannot be Terraform-generated, populated manually out-of-band."
  type        = list(string)
  default     = ["food-recognition-service"]
}

# --- Scale-to-zero ---

variable "scale_down_schedule_expression" {
  type    = string
  default = "cron(0 20 ? * MON-FRI *)"
}

variable "scale_up_schedule_expression" {
  type    = string
  default = "cron(0 7 ? * MON-FRI *)"
}

variable "schedule_timezone" {
  type    = string
  default = "UTC"
}
