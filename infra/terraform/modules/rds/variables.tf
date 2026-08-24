# infra/terraform/modules/rds/variables.tf
#
# One shared PostgreSQL instance for all services (docs/terraform-and-
# infrastructure.md section 3). Per-service logical databases/roles are
# NOT created here — see infra/k8s/charts/_lib/templates/_db-provision-job.tpl
# and the implementation plan section 9.1 for why (no network path from
# Terraform's postgresql provider into the private-subnet instance).

variable "identifier" {
  description = "RDS instance identifier."
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security group IDs allowed to connect to Postgres on 5432 (typically the EKS cluster's primary security group)."
  type        = list(string)
}

variable "engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16.4"
}

variable "parameter_group_family" {
  type    = string
  default = "postgres16"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Initial storage in GB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Storage autoscaling ceiling in GB (0 disables autoscaling)."
  type        = number
  default     = 100
}

variable "multi_az" {
  description = "Multi-AZ deployment. false for dev (single-AZ, per cost table); must be true for prod."
  type        = bool
  default     = false
}

variable "master_username" {
  type    = string
  default = "nutriapp_admin"
}

variable "backup_retention_period" {
  description = "Automated backup retention in days."
  type        = number
  default     = 7
}

variable "backup_window" {
  type    = string
  default = "05:00-06:00"
}

variable "maintenance_window" {
  type    = string
  default = "sun:06:30-sun:07:30"
}

variable "deletion_protection" {
  description = "false for dev (allows teardown), must be true for staging/prod."
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "true for dev (disposable), must be false for staging/prod."
  type        = bool
  default     = true
}

variable "apply_immediately" {
  type    = bool
  default = true
}

variable "port" {
  type    = number
  default = 5432
}

variable "tags" {
  type    = map(string)
  default = {}
}
