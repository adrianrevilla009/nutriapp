# infra/terraform/bootstrap/versions.tf
#
# Bootstrap is a standalone root module (local state, applied once,
# manually, by a human) that creates the S3 bucket + DynamoDB table every
# other environment's remote state depends on. It cannot itself use a
# remote backend (chicken-and-egg problem) — see README.md.

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Intentionally no `backend` block: this state stays local, per
  # README.md. Do not add an S3 backend here.
}
