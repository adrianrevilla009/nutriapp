# infra/terraform/environments/dev/backend.tf
#
# Partial backend configuration — bucket/key/region/dynamodb_table are
# supplied at `terraform init -backend-config=backend.hcl` time, not
# hardcoded here, because the bucket name is account-specific (derived
# from the AWS account ID by infra/terraform/bootstrap) and must not be
# guessed/hardcoded in committed code. See README.md and
# backend.hcl.example.

terraform {
  backend "s3" {
    key     = "dev/terraform.tfstate"
    encrypt = true
  }
}
