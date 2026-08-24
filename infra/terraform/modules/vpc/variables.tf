# infra/terraform/modules/vpc/variables.tf
#
# Environment-agnostic: no hardcoded env names, account IDs, or CIDR
# ranges — everything comes from the caller (environments/<env>/).

variable "name" {
  description = "Name prefix for all resources in this VPC (e.g. \"nutriapp-dev\")."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "availability_zones" {
  description = "List of AZs to spread subnets across (docs/terraform-and-infrastructure.md section 3 requires 3 AZs)."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least 2 availability zones are required; 3 is the documented standard."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (ALB, NAT gateways only), one per AZ."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (EKS nodes, RDS, ElastiCache, RabbitMQ, Qdrant), one per AZ."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "Use a single NAT gateway for all private subnets instead of one per AZ. Trades HA for cost — true is the accepted dev default (docs/terraform-and-infrastructure.md section 3), false is required for staging/prod-like HA."
  type        = bool
  default     = false
}

variable "cluster_name" {
  description = "EKS cluster name used to tag subnets for auto-discovery by the cluster and the AWS Load Balancer Controller (kubernetes.io/cluster/<name> and kubernetes.io/role/* tags). Pass null to skip these tags."
  type        = string
  default     = null
}

variable "tags" {
  description = "Common tags merged into every resource (Project, Environment, ManagedBy, CostCenter are expected to already be supplied here or via provider default_tags; this module additionally sets Service=shared and per-resource Name tags)."
  type        = map(string)
  default     = {}
}
