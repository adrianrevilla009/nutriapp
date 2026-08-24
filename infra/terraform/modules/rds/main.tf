# infra/terraform/modules/rds/main.tf

locals {
  base_tags = merge(var.tags, {
    Service = "shared"
  })
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.identifier}-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(local.base_tags, {
    Name = "${var.identifier}-subnet-group"
  })
}

resource "aws_security_group" "this" {
  name        = "${var.identifier}-rds"
  description = "Allow Postgres access from the EKS cluster only."
  vpc_id      = var.vpc_id

  # No egress at all: RDS itself never initiates outbound connections, so
  # egress is explicitly denied rather than left at AWS's implicit
  # allow-all default (checkov CKV_AWS_382). Ingress is managed
  # separately below via aws_security_group_rule.
  egress = []

  tags = merge(local.base_tags, {
    Name = "${var.identifier}-rds"
  })
}

resource "aws_security_group_rule" "ingress" {
  # `count`, not `for_each`/toset(): var.allowed_security_group_ids's
  # values (typically module.eks.cluster_primary_security_group_id) are
  # unknown until the EKS cluster is actually created on a from-scratch
  # apply — for_each requires knowing the full set of KEYS at plan time,
  # which an unknown value can't provide, while count only needs the
  # (statically known) length of the list.
  count                    = length(var.allowed_security_group_ids)
  type                     = "ingress"
  from_port                = var.port
  to_port                  = var.port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.this.id
  source_security_group_id = var.allowed_security_group_ids[count.index]
  description              = "Postgres from EKS security group ${count.index}"
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.identifier}-pg"
  family = var.parameter_group_family

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  # Force TLS between clients (service pods, the db-provision-job) and
  # this instance — encryption in transit, not just at rest (checkov
  # CKV2_AWS_69).
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = local.base_tags
}

# Master credential: RDS-managed (manage_master_user_password = true) —
# AWS generates and stores the password directly in Secrets Manager, it
# is never visible in this configuration or written to a .tf/.tfvars
# file (ADR-0007, implementation plan section 9.4). AWS handles rotation
# of this specific secret natively.
resource "aws_db_instance" "this" {
  identifier     = var.identifier
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  parameter_group_name   = aws_db_parameter_group.this.name
  port                   = var.port

  multi_az = var.multi_az

  username                    = var.master_username
  manage_master_user_password = true

  backup_retention_period = var.backup_retention_period
  backup_window           = var.backup_window
  maintenance_window      = var.maintenance_window

  # checkov:skip=CKV_AWS_293:var.deletion_protection defaults false only for dev (allows teardown of disposable dev infra); must be — and per this module's variables.tf docstring, is required to be — true for staging/prod.
  # checkov:skip=CKV_AWS_157:var.multi_az defaults false only for dev, a deliberate documented cost decision (implementation plan section 7's cost table, docs/terraform-and-infrastructure.md section 3); staging mirrors prod topology, prod requires Multi-AZ.
  # checkov:skip=CKV_AWS_353:Performance Insights support on the smallest burstable instance classes (dev's default db.t4g.micro) is inconsistent across engine versions — not worth risking an apply-time failure to verify; revisit once staging/prod use a larger instance_class.
  # checkov:skip=CKV_AWS_118:Enhanced Monitoring adds a small perpetual cost and an extra IAM role for limited value on an instance that's stopped outside working hours anyway (modules/scale-to-zero); revisit for staging/prod.
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.identifier}-final"
  apply_immediately         = var.apply_immediately

  auto_minor_version_upgrade = true
  copy_tags_to_snapshot      = true

  # Enables IAM-token-based auth as an ADDITIONAL option (opt-in per DB
  # role via `GRANT rds_iam`) alongside the existing password-based auth
  # the db-provision-job and services already use — not a breaking
  # change, just an available future path for short-lived human/admin
  # access without a long-lived password.
  iam_database_authentication_enabled = true

  # Publish Postgres logs to CloudWatch (checkov CKV_AWS_129) — pairs with
  # log_min_duration_statement above.
  enabled_cloudwatch_logs_exports = ["postgresql"]

  # NOTE: Performance Insights (CKV_AWS_353) and Enhanced Monitoring
  # (CKV_AWS_118) are deliberately NOT enabled for dev's default
  # db.t4g.micro instance class — Performance Insights support on the
  # smallest burstable instance classes is inconsistent across engine
  # versions and this is not worth risking an apply-time failure to
  # verify; Enhanced Monitoring adds a small perpetual cost for limited
  # value on a scale-to-zero'd dev instance. Both are one-line additions
  # (a `performance_insights_enabled = true` and a monitoring IAM
  # role + `monitoring_interval`) worth revisiting once staging/prod use
  # a larger instance_class.

  tags = merge(local.base_tags, {
    Name = var.identifier
  })

  # NOTE: the scale-to-zero Lambda (modules/scale-to-zero) stops/starts
  # this instance outside working hours in dev via the RDS API directly
  # (not via Terraform), and AWS auto-restarts a stopped instance after
  # ~7 days regardless. Neither changes any attribute Terraform manages,
  # so no `ignore_changes` is required for `status` drift.
}
