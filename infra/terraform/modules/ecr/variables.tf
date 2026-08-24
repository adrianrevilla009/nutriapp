# infra/terraform/modules/ecr/variables.tf

variable "repository_name" {
  description = "ECR repository name, e.g. \"nutriapp/identity-service\" or \"nutriapp/db-provision\" for a shared platform utility image."
  type        = string
}

variable "kms_key_id" {
  description = "KMS key ARN/ID for image encryption at rest. null uses the AWS-managed aws/ecr key."
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
