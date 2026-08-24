# infra/terraform/modules/eks/variables.tf

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version. Keep current against AWS's supported-versions list (checkov CKV_AWS_339) — check at apply time, not just at the time this default was written."
  type        = string
  default     = "1.32"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  description = "Private subnets nodes run in."
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnets, included in cluster vpc_config for the public endpoint's ENI placement per the public+private access decision (implementation plan section 9.3)."
  type        = list(string)
}

variable "cluster_endpoint_public_access_cidrs" {
  description = <<-EOT
    CIDR blocks allowed to reach the EKS public API endpoint. Resolved
    decision (implementation plan section 9.3): public+private access,
    restricted to the operator's current IP rather than a bastion/VPN.
    No default of 0.0.0.0/0 is provided deliberately — the caller must
    supply this explicitly and keep it current as the operator's IP
    changes.
  EOT
  type        = list(string)

  validation {
    condition     = !contains(var.cluster_endpoint_public_access_cidrs, "0.0.0.0/0")
    error_message = "0.0.0.0/0 is not allowed for cluster_endpoint_public_access_cidrs — restrict to the operator's known IP(s) per the implementation plan section 9.3."
  }
}

variable "on_demand_instance_types" {
  description = "Instance types for the on-demand baseline node group. Must match the architecture implied by var.ami_type (default AL2_ARM_64 -> Graviton t4g family)."
  type        = list(string)
  default     = ["t4g.medium"]
}

variable "on_demand_desired_size" {
  type    = number
  default = 1
}

variable "on_demand_min_size" {
  type    = number
  default = 0
}

variable "on_demand_max_size" {
  type    = number
  default = 3
}

variable "spot_instance_types" {
  description = "Instance types for the spot burst node group (interruption-tolerant workloads only, e.g. async event projectors). Kept single-architecture (Graviton, matching var.ami_type's default) rather than mixing arm64/x86_64 instance families in one node group."
  type        = list(string)
  default     = ["t4g.medium", "t4g.large"]
}

variable "spot_desired_size" {
  type    = number
  default = 0
}

variable "spot_min_size" {
  type    = number
  default = 0
}

variable "spot_max_size" {
  type    = number
  default = 5
}

variable "ami_type" {
  description = "EKS-optimized AMI type for node groups."
  type        = string
  default     = "AL2_ARM_64"
}

variable "capacity_type_on_demand" {
  type    = string
  default = "ON_DEMAND"
}

variable "tags" {
  type    = map(string)
  default = {}
}
