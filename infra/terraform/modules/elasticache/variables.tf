# infra/terraform/modules/elasticache/variables.tf

variable "name" {
  description = "ElastiCache replication group identifier."
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security group IDs allowed to connect on the Redis port (typically the EKS cluster's primary security group)."
  type        = list(string)
}

variable "node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "engine_version" {
  type    = string
  default = "7.1"
}

variable "parameter_group_family" {
  type    = string
  default = "redis7"
}

variable "num_cache_clusters" {
  description = "1 for dev (single node, no replica). cluster mode / multiple replicas is a prod concern per docs/terraform-and-infrastructure.md section 3."
  type        = number
  default     = 1
}

variable "port" {
  type    = number
  default = 6379
}

variable "secrets_kms_key_id" {
  description = "Optional KMS key ARN for the Secrets Manager secret holding the auth token. null uses the default aws/secretsmanager key."
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
