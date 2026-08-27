# infra/terraform/bootstrap/main.tf
#
# One-time, human-applied bootstrap: the S3 bucket + DynamoDB lock table
# that every `environments/<env>/` remote state backend points at. See
# README.md for the exact manual init/plan/apply runbook. Per CLAUDE.md
# section 7 and .claude/hooks/pre-terraform-guard.sh, an agent NEVER runs
# `terraform apply` here or anywhere else — only `terraform plan`.

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = "shared"
      Service     = "shared"
      ManagedBy   = "terraform"
      CostCenter  = "platform-shared"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  # Deterministic, globally-unique bucket name derived from the account ID
  # (dynamic — never a hardcoded account ID literal in code) rather than a
  # random suffix, so re-running bootstrap in the same account is
  # idempotent and predictable.
  state_bucket_name = "nutriapp-tfstate-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  lock_table_name   = "nutriapp-tfstate-lock"
}

resource "aws_s3_bucket" "state" { # NOSONAR: access logging deliberately omitted, same rationale as CKV_AWS_18 below
  bucket = local.state_bucket_name

  # Deliberately no `force_destroy` — losing this bucket orphans every
  # environment's state. Human must empty it explicitly if it is ever to
  # be destroyed (and destroy is never run by an agent regardless).

  # checkov:skip=CKV_AWS_18:Access logging needs a second bucket to receive logs — disproportionate operational overhead for a single bootstrap-only state bucket at this project's scale; CloudTrail already covers API-level access auditing for this bucket.
  # checkov:skip=CKV_AWS_144:Cross-region replication doubles storage cost and adds a second bucket/region for a bucket that already has versioning + point-in-time-recoverable DynamoDB locking; revisit if/when multi-region DR (docs/multi-region-strategy.md) is actually triggered.
  # checkov:skip=CKV2_AWS_62:Event notifications have no consumer today (no SNS/SQS/Lambda wired to react to state-file changes) — low value for a bootstrap-only bucket; add if a future automation needs to react to state changes.
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Bounds storage growth from state file version history (versioning is
# enabled above so a bad apply is always recoverable) without discarding
# it immediately — 90 days of noncurrent versions, then expire.
resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Deny any non-TLS access to the state bucket — Terraform state can
# contain sensitive values (e.g. RDS-managed secret ARNs, generated
# passwords for resources like the ElastiCache auth token) even though we
# avoid literal secrets in .tf/.tfvars.
resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.state.arn,
          "${aws_s3_bucket.state.arn}/*",
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

resource "aws_dynamodb_table" "lock" {
  name         = local.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  # AWS-managed KMS key (aws/dynamodb) rather than the AWS-owned default —
  # a strict improvement at no additional cost for a table this small.
  # checkov:skip=CKV_AWS_119:A dedicated customer-managed CMK (as opposed to the AWS-managed key configured below) is disproportionate for a lock table holding no application data, only lock metadata.
  server_side_encryption {
    enabled = true
  }
}
