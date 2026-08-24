# infra/terraform/modules/scale-to-zero/main.tf

locals {
  base_tags = merge(var.tags, {
    Service = "shared"
  })
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/scale_handler.py"
  output_path = "${path.module}/lambda/scale_handler.zip"
}

resource "aws_iam_role" "lambda" {
  name = "${var.name_prefix}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.base_tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

locals {
  # EKS nodegroup ARN format:
  # arn:aws:eks:<region>:<account>:nodegroup/<cluster>/<nodegroup-name>/<uuid>
  # — scoped to exactly this cluster's known node groups rather than "*"
  # (checkov CKV_AWS_356 / CKV_AWS_111).
  node_group_arns = [
    for ng_name in keys(var.node_group_baselines) :
    "arn:aws:eks:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:nodegroup/${var.cluster_name}/${ng_name}/*"
  ]
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid    = "ScaleEksNodeGroups"
    effect = "Allow"
    actions = [
      "eks:DescribeNodegroup",
      "eks:UpdateNodegroupConfig",
    ]
    resources = local.node_group_arns
  }

  statement {
    sid    = "StopStartRds"
    effect = "Allow"
    actions = [
      "rds:StopDBInstance",
      "rds:StartDBInstance",
      "rds:DescribeDBInstances",
    ]
    resources = [var.rds_instance_arn]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "scale-to-zero"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "this" {
  function_name = var.name_prefix
  role          = aws_iam_role.lambda.arn
  handler       = "scale_handler.handler"
  runtime       = "python3.12"
  timeout       = var.lambda_timeout_seconds

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  # Never more than one concurrent invocation: overlapping scale_down /
  # scale_up runs racing against each other is a real correctness risk,
  # not just a security-scanner nit (checkov CKV_AWS_115).
  reserved_concurrent_executions = 1

  environment {
    variables = {
      CLUSTER_NAME         = var.cluster_name
      RDS_INSTANCE_ID      = var.rds_instance_id
      NODE_GROUP_BASELINES = jsonencode(var.node_group_baselines)
    }
  }

  tags = local.base_tags

  # checkov:skip=CKV_AWS_272:Code-signing overhead (a dedicated Signing Profile) is disproportionate for a small internal cost-automation function; revisit if this pattern is reused for anything customer-facing.
  # checkov:skip=CKV_AWS_116:No DLQ — a missed scale_down/scale_up cycle degrades to "dev costs a bit more this cycle", not data loss; CloudWatch Logs (below) already captures failures for manual follow-up.
  # checkov:skip=CKV_AWS_173:Lambda environment variables here are non-secret (cluster name, RDS instance ID, node group sizing) — default AWS-managed-key encryption already applies; a dedicated CMK is disproportionate.
  # checkov:skip=CKV_AWS_50:X-Ray tracing adds cost/complexity not justified for a low-frequency, non-customer-facing internal cron function.
  # checkov:skip=CKV_AWS_117:Deliberately NOT in the VPC — this function only calls regional AWS control-plane APIs (EKS, RDS), never talks to anything inside the VPC; adding VPC config would add ENI/NAT overhead and cold-start latency for no benefit.
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.name_prefix}"
  retention_in_days = 14

  tags = local.base_tags

  # checkov:skip=CKV_AWS_338:14-day retention (matching the VPC flow logs) is sufficient for a low-value dev-only automation function's operational debugging — 1-year retention is a real, ongoing storage cost with no corresponding audit/compliance requirement here (unlike the audit trail in CLAUDE.md section 2.8, which this log group is not part of).
  # checkov:skip=CKV_AWS_158:Default CloudWatch Logs encryption (AWS-owned key) already applies; a dedicated CMK adds cost/complexity disproportionate to this log group's low sensitivity (no secrets are ever logged here, per docs/secrets-management.md section 5).
}

# --- Scheduling (EventBridge Scheduler) -----------------------------------

resource "aws_iam_role" "scheduler" {
  name = "${var.name_prefix}-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.base_tags
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "invoke-lambda"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.this.arn
      }
    ]
  })
}

resource "aws_scheduler_schedule" "scale_down" {
  # checkov:skip=CKV_AWS_297:Default AWS-owned key encryption already applies to the schedule payload (a fixed, non-secret {"action": "scale_down"} literal); a dedicated CMK is disproportionate for this dev-only cost-automation schedule.
  name       = "${var.name_prefix}-scale-down"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = var.scale_down_schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = aws_lambda_function.this.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ action = "scale_down" })
  }
}

resource "aws_scheduler_schedule" "scale_up" {
  # checkov:skip=CKV_AWS_297:Same justification as scale_down above.
  name       = "${var.name_prefix}-scale-up"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = var.scale_up_schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = aws_lambda_function.this.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ action = "scale_up" })
  }
}

resource "aws_lambda_permission" "allow_scheduler_scale_down" {
  statement_id  = "AllowEventBridgeSchedulerInvokeScaleDown"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.scale_down.arn
}

resource "aws_lambda_permission" "allow_scheduler_scale_up" {
  statement_id  = "AllowEventBridgeSchedulerInvokeScaleUp"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.scale_up.arn
}
