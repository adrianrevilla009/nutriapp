# infra/terraform/bootstrap/variables.tf

variable "aws_region" {
  description = "AWS region the state bucket and lock table live in."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project tag applied to every resource (docs/terraform-and-infrastructure.md section 5)."
  type        = string
  default     = "nutriapp"
}
