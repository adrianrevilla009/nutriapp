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
  type    = list(string)
  default = ["identity-service", "profile-service"]
}

variable "internal_reveal_credential_service_names" {
  type    = list(string)
  default = ["identity-service"]
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
